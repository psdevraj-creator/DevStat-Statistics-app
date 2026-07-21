import React, { useState, useEffect, useMemo } from 'react'
import {
  Card, Button, Select, Checkbox, Tabs, Space, Typography, message, Spin, Table, Alert,
  Input, Divider, Tag, Tooltip,
} from 'antd'
import { PlayCircleOutlined, CalculatorOutlined, SwapOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import EligibilityAlert from '../components/EligibilityAlert'
import ErrorDisplay from '../components/ErrorDisplay'
import { useEligibilityCheck } from '../hooks/useEligibility'
import Plot from '../utils/plotlyWrap'
import ErrorBoundary from '../components/ErrorBoundary'
import { survivalApi, datasetApi, api } from '../api/client'

import outputStore from '../stores/outputStore'
import logStore from '../stores/logStore'
import { formatApiError } from '../utils/errors'

const { Text, Title } = Typography

const SurvivalPage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<string>('km')
  const [timeVar, setTimeVar] = useState<string | undefined>(undefined)
  const [statusVar, setStatusVar] = useState<string | undefined>(undefined)
  const [factor, setFactor] = useState<string | undefined>(undefined)
  const [covariates, setCovariates] = useState<string[]>([])
  const [showCurve, setShowCurve] = useState(true)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [kmGraph, setKmGraph] = useState<any>(null)
  const [forestGraph, setForestGraph] = useState<any>(null)
  const [predictGraph, setPredictGraph] = useState<any>(null)
  const [analysisError, setAnalysisError] = useState<any>(null)
  const [adjustedExposure, setAdjustedExposure] = useState<string | undefined>(undefined)
  const [adjustedExposure2, setAdjustedExposure2] = useState<string | undefined>(undefined)
  const [adjustedGraph, setAdjustedGraph] = useState<any>(null)
  const [adjustedLoading, setAdjustedLoading] = useState(false)
  const [adjusterValues, setAdjusterValues] = useState<Record<string, string>>({})

  // ── Data prep state ──
  const [startCol, setStartCol] = useState<string | undefined>(undefined)
  const [eventDateCol, setEventDateCol] = useState<string | undefined>(undefined)
  const [censorDateCol, setCensorDateCol] = useState<string | undefined>(undefined)
  const [prepUnit, setPrepUnit] = useState<string>('months')
  const [prepDayFirst, setPrepDayFirst] = useState(false)
  const [prepTimeCol, setPrepTimeCol] = useState<string>('survival_time')
  const [prepStatusCol, setPrepStatusCol] = useState<string>('event_status')
  const [prepLoading, setPrepLoading] = useState(false)
  const [prepResult, setPrepResult] = useState<any>(null)

  const eligParams = useMemo(() => ({
    analysis: activeTab === 'km' ? 'survival' : 'survival',
    var_types: {},
    has_time: !!timeVar, has_event: !!statusVar,
  }), [activeTab, timeVar, statusVar])
  const eligibility = useEligibilityCheck(timeVar && statusVar ? eligParams : null)

  useEffect(() => { loadDatasets() }, [])
  useEffect(() => { if (selectedDataset) loadColumns() }, [selectedDataset])

  const loadDatasets = async () => {
    try {
      const res = await datasetApi.list()
      const ds = res.data || []
      setDatasets(ds)
      if (ds.length > 0 && !selectedDataset) setSelectedDataset(ds[0].id)
    } catch { message.warning('Failed to load datasets') }
  }
  
  const loadColumns = async () => {
    try { const res = await datasetApi.columns(selectedDataset); setColumns(res.data.columns || res.data || []) } catch { message.warning('Failed to load columns') }
  }

  // ── Fix mixed date formats ──
  const handleFixDates = async () => {
    if (!startCol && !eventDateCol && !censorDateCol) {
      message.warning('Select at least one date column first')
      return
    }
    const cols = [startCol, eventDateCol, censorDateCol].filter(Boolean) as string[]
    setPrepLoading(true)
    let totalFixed = 0, totalAlready = 0
    try {
      for (const col of cols) {
        const res = await (api as any).post('/api/data/fix-dates', {
          column: col,
          dayfirst: prepDayFirst,
        })
        totalFixed += res.data.fixed || 0
        totalAlready += res.data.already_valid || 0
      }
      await loadColumns()
      message.success(`Dates fixed: ${totalFixed} converted, ${totalAlready} already valid`)
    } catch (err: any) {
      message.error('Fix dates failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setPrepLoading(false)
    }
  }

  // ── Survival Data Preparation ──
  const handleSurvivalPrep = async () => {
    if (!startCol || !eventDateCol || !censorDateCol) {
      message.warning('Select all three date columns: start, event, and censor')
      return
    }
    setPrepLoading(true)
    setPrepResult(null)
    try {
      const res = await (api as any).post('/api/data/survival-prep', {
        start_col: startCol,
        event_col: eventDateCol,
        censor_col: censorDateCol,
        unit: prepUnit,
        dayfirst: prepDayFirst,
        new_time_col: prepTimeCol,
        new_status_col: prepStatusCol,
      })
      setPrepResult(res.data)
      // Auto-select the new columns for analysis
      setTimeVar(prepTimeCol)
      setStatusVar(prepStatusCol)
      // Refresh column list
      await loadColumns()
      message.success(`Survival data prepared: ${res.data.n_events} events, ${res.data.n_censored} censored`)
    } catch (err: any) {
      message.error('Prep failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setPrepLoading(false)
    }
  }

  const runAnalysis = async () => {
    if (!selectedDataset || !timeVar || !statusVar) {
      message.warning('Please select time and status variables')
      return
    }
    setLoading(true)
    setKmGraph(null); setForestGraph(null); setPredictGraph(null); setAdjustedGraph(null); setAnalysisError(null)
    try {
      let res
      if (activeTab === 'km') {
        res = await survivalApi.kaplanMeier(selectedDataset, timeVar, statusVar, factor)
        const kmData = res.data
        setResults(kmData)
        outputStore.addEntry('survival', 'Kaplan-Meier', kmData)
        if (kmData.error) {
          message.error(kmData.error)
        } else {
          message.success('Analysis complete')
        }
        if (kmData.series && Array.isArray(kmData.series) && kmData.series.length > 0) {
          setKmGraph({
            data: kmData.series.map((s: any) => ({
              type: 'scatter', mode: 'lines',
              name: s.group || 'All',
              x: s.x, y: s.y,
              line: { shape: 'hv' },
            })),
            layout: {
              title: 'Kaplan-Meier Survival Curves',
              xaxis: { title: 'Time' },
              yaxis: { title: 'Survival Probability', range: [0, 1] },
            },
          })
        } else {
          logStore.addEntry('render', 'KM_graph', 'series missing or empty', '', {
            has_series: !!kmData.series,
            is_array: Array.isArray(kmData.series),
            length: kmData.series?.length,
            keys: Object.keys(kmData),
          })
        }
      } else {
        if (covariates.length === 0) { message.warning('Please select at least one covariate'); setLoading(false); return }
        res = await survivalApi.coxRegression(selectedDataset, timeVar, statusVar, covariates)
        setResults(res.data)
        outputStore.addEntry('survival', 'Cox Regression', res.data)
        message.success('Analysis complete')
        // Extract coefficients from transformed response (top-level)
        const coxCoefficients = res.data?.coefficients || []
        try {
          if (coxCoefficients.length > 0) {
            const fRes = await survivalApi.forestPlot(coxCoefficients)
            if (fRes.data?.traces) setForestGraph({ data: fRes.data.traces, layout: fRes.data.layout })
          }
        } catch (e) { console.warn('[SurvivalPage] forest plot error:', e) }
        try {
          const pRes = await survivalApi.predictSurvival(timeVar, statusVar, covariates)
          if (pRes.data?.traces) setPredictGraph({ data: pRes.data.traces, layout: pRes.data.layout })
        } catch (e) { console.warn('[SurvivalPage] predict survival error:', e) }
      }
    } catch (err: any) {
      setAnalysisError(err?.response?.data || { message: formatApiError(err, 'Analysis failed'), suggestion: 'Check your variable selections and try again.' })
    } finally { setLoading(false) }
  }

  const handleAdjustedSurvival = async () => {
    if (!adjustedExposure) { message.warning('Select exposure variable'); return }
    setAdjustedLoading(true)
    try {
      const adjCols = covariates.filter(c => c !== adjustedExposure && c !== adjustedExposure2)
      const overrides = Object.fromEntries(Object.entries(adjusterValues).filter(([, v]) => v.trim() !== ''))
      const res = await survivalApi.adjustedSurvival(timeVar!, statusVar!, adjustedExposure, adjCols, overrides, adjustedExposure2)
      if (res.data?.traces) setAdjustedGraph({ data: res.data.traces, layout: res.data.layout })
      message.success('Adjusted survival curves generated')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err.message)
    } finally { setAdjustedLoading(false) }
  }

  const renderResults = () => {
    if (!results) return null
    const data = results.data || results.results || results
    if (Array.isArray(data)) {
      const cols = Object.keys(data[0] || {}).map(key => ({
        title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        dataIndex: key, key,
        render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-',
      }))
      return <Table dataSource={data} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered />
    }
    if (data.table || data.summary_table) {
      const table = data.table || data.summary_table
      if (Array.isArray(table)) {
        const cols = Object.keys(table[0] || {}).map(key => ({
          title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
          dataIndex: key, key,
          render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-',
        }))
        return <Table dataSource={table} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered />
      }
    }
    const rows: { metric: string; value: string }[] = []
    if (data.median_survival !== undefined) {
      if (Array.isArray(data.median_survival)) {
        data.median_survival.forEach((m: any) => {
          rows.push({ metric: `Median (${m.group || 'overall'})`, value: m.median != null ? String(m.median) : 'N/A' })
        })
      } else {
        rows.push({ metric: 'Median Survival', value: String(data.median_survival) })
      }
    }
    if (data.chisq !== undefined) rows.push({ metric: 'Chi-square', value: String(data.chisq) })
    if (data.p_value !== undefined) rows.push({ metric: 'P-value', value: String(data.p_value) })
    if (data.hazard_ratio !== undefined) rows.push({ metric: 'Hazard Ratio', value: String(data.hazard_ratio) })
    if (data.concordance !== undefined) rows.push({ metric: 'Concordance', value: String(data.concordance) })
    if (rows.length > 0) {
      return <Table dataSource={rows} columns={[{ title: 'Metric', dataIndex: 'metric' }, { title: 'Value', dataIndex: 'value' }]} rowKey="metric" pagination={false} size="small" bordered />
    }
    return (
      <Alert type="warning" message="Unrecognized result format"
        description="The analysis completed but the result shape is not supported by the current renderer."
        style={{ marginTop: 16 }} />
    )
  }

  const renderInterpretation = () => {
    if (!results) return null
    const interp = results.interpretation || results.summary
    if (!interp) return null
    return (
      <Alert type="info" message="Interpretation"
        description={typeof interp === 'string' ? interp : JSON.stringify(interp, null, 2)}
        style={{ marginTop: 16, background: '#f0f7ff', border: '1px solid #bae0ff' }} />
    )
  }

  const plotlyConfig = {
    displayModeBar: true, displaylogo: false, responsive: true,
    modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
    toImageButtonOptions: { format: 'png', filename: 'devstat-chart', width: 1200, height: 800 },
  }

  const renderCoxGraphs = () => {
    if (activeTab !== 'cox') return null
    return (
      <>
        {forestGraph && showCurve && (
          <ErrorBoundary>
            <Card title="Forest Plot" style={{ marginTop: 16, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}>
              <Plot data={forestGraph.data} layout={forestGraph.layout} config={{ ...plotlyConfig, responsive: true }}
                useResizeHandler style={{ width: '100%', height: 320 }} />
            </Card>
          </ErrorBoundary>
        )}
        {predictGraph && showCurve && (
          <ErrorBoundary>
            <Card title="Predicted Survival Curves" style={{ marginTop: 16, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}>
              <Plot data={predictGraph.data} layout={predictGraph.layout} config={{ ...plotlyConfig, responsive: true }}
                useResizeHandler style={{ width: '100%', height: 450 }} />
            </Card>
          </ErrorBoundary>
        )}
      </>
    )
  }

  const renderVariableSelectors = () => (
    activeTab === 'km' ? (
      <Space><Text style={{ width: 120 }}>Factor (optional):</Text>
        <Select style={{ width: 300 }} placeholder="Optional grouping" allowClear value={factor} onChange={setFactor}
          options={columns.map(c => ({ label: c, value: c }))} /></Space>
    ) : (
      <Space><Text style={{ width: 120 }}>Covariates:</Text>
        <Select mode="multiple" style={{ width: 350 }} placeholder="Select covariates" value={covariates} onChange={setCovariates}
          options={columns.map(c => ({ label: c, value: c }))} /></Space>
    )
  )

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Survival Analysis</Title>

      {/* ── Survival Data Preparation ── */}
      <Card
        title={
          <Space>
            <CalculatorOutlined style={{ color: '#005eb8' }} />
            <span>Survival Data Preparation</span>
            <Tag color="blue" style={{ fontSize: 10 }}>from dates</Tag>
          </Space>
        }
        style={{ marginBottom: 16, borderLeft: '3px solid #005eb8' }}
      >
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 16 }}>
          Automatically compute survival time and event/censor status from raw date columns.
          Select your date of origin, date of event (death), and date of last follow-up.
        </Text>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <div>
            <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Dataset:</Text>
            <Select style={{ width: 300 }} placeholder="Select dataset first" 
              value={selectedDataset || undefined} onChange={(v) => { setSelectedDataset(v); setPrepResult(null); }}
              options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))} />
          </div>
          {columns.length === 0 && selectedDataset && (
            <Text type="secondary" style={{ fontSize: 11 }}>Loading columns...</Text>
          )}
          <Space wrap>
            <div>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Date of Origin:</Text>
              <Select style={{ width: 220 }} placeholder="e.g. diagnosis date"
                value={startCol} onChange={setStartCol} showSearch disabled={columns.length === 0}
                options={columns.map(c => ({ label: c, value: c }))} />
            </div>
            <div>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Date of Event (death):</Text>
              <Select style={{ width: 220 }} placeholder="e.g. date of death"
                value={eventDateCol} onChange={setEventDateCol} showSearch disabled={columns.length === 0}
                options={columns.map(c => ({ label: c, value: c }))} />
            </div>
            <div>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Date of Last Follow-up:</Text>
              <Select style={{ width: 220 }} placeholder="e.g. last contact date"
                value={censorDateCol} onChange={setCensorDateCol} showSearch disabled={columns.length === 0}
                options={columns.map(c => ({ label: c, value: c }))} />
            </div>
          </Space>
          <Space wrap>
            <div>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Time Unit:</Text>
              <Select style={{ width: 120 }} value={prepUnit} onChange={setPrepUnit}
                options={[
                  { label: 'Days', value: 'days' },
                  { label: 'Months', value: 'months' },
                  { label: 'Years', value: 'years' },
                ]} />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 2 }}>
              <Checkbox checked={prepDayFirst} onChange={e => setPrepDayFirst(e.target.checked)}>
                <span style={{ fontSize: 12 }}>Day first (DD/MM/YYYY)</span>
              </Checkbox>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Tooltip title="Standardize all selected date columns to YYYY-MM-DD format. Tries both day/month orderings for each value.">
                <Button size="small" icon={<SwapOutlined />} onClick={handleFixDates} loading={prepLoading}
                  disabled={!startCol && !eventDateCol && !censorDateCol}>
                  Fix Date Formats
                </Button>
              </Tooltip>
            </div>
            <div>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Output Time Column:</Text>
              <Input style={{ width: 160 }} value={prepTimeCol} onChange={e => setPrepTimeCol(e.target.value)}
                placeholder="survival_time" />
            </div>
            <div>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Output Status Column:</Text>
              <Input style={{ width: 160 }} value={prepStatusCol} onChange={e => setPrepStatusCol(e.target.value)}
                placeholder="event_status" />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Button type="primary" icon={<CalculatorOutlined />}
                onClick={handleSurvivalPrep} loading={prepLoading}>
                Prepare Survival Data
              </Button>
            </div>
          </Space>
        </Space>

        {prepResult && (
          <div style={{
            marginTop: 16, padding: '12px 16px', background: '#f0fdf4', borderRadius: 6,
            border: '1px solid #bbf7d0', display: 'flex', gap: 24, flexWrap: 'wrap',
          }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Events</Text>
              <div><Text strong style={{ fontSize: 18, color: '#166534' }}>{prepResult.n_events}</Text></div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Censored</Text>
              <div><Text strong style={{ fontSize: 18, color: '#854d0e' }}>{prepResult.n_censored}</Text></div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Mean Time ({prepUnit})</Text>
              <div><Text strong style={{ fontSize: 18, color: '#1e40af' }}>{prepResult.mean_time ?? 'N/A'}</Text></div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>New Columns</Text>
              <div>
                <Tag color="green">{prepResult.new_time_col}</Tag>
                <Tag color="blue">{prepResult.new_status_col}</Tag>
              </div>
            </div>
          </div>
        )}
        {prepResult?.diagnostics && (
          <div style={{
            marginTop: 8, padding: '8px 12px', background: '#f8fafc', borderRadius: 4,
            fontSize: 11, color: '#64748b',
          }}>
            Date parsing: {prepResult.diagnostics.start_parsed}/{prepResult.diagnostics.total_rows} start,
            {prepResult.diagnostics.event_parsed}/{prepResult.diagnostics.total_rows} event,
            {prepResult.diagnostics.censor_parsed}/{prepResult.diagnostics.total_rows} censor dates parsed
            {prepResult.diagnostics.dayfirst ? ' (DD/MM/YYYY)' : ' (MM/DD/YYYY)'}
          </div>
        )}
      </Card>

      <Card title="Configuration" style={{ marginBottom: 16 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          { key: 'km', label: 'Kaplan-Meier' },
          { key: 'cox', label: 'Cox Regression' },
        ]} />

        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space><Text style={{ width: 120 }}>Dataset:</Text>
            <Select style={{ width: 300 }} placeholder="Select dataset" value={selectedDataset || undefined} onChange={setSelectedDataset}
              options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))} /></Space>
          <Space><Text style={{ width: 120 }}>Time variable:</Text>
            <Select style={{ width: 300 }} placeholder="Select time" value={timeVar} onChange={setTimeVar}
              options={columns.map(c => ({ label: c, value: c }))} /></Space>
          <Space><Text style={{ width: 120 }}>Status variable:</Text>
            <Select style={{ width: 300 }} placeholder="Select status (event)" value={statusVar} onChange={setStatusVar}
              options={columns.map(c => ({ label: c, value: c }))} /></Space>
          {renderVariableSelectors()}
          <Checkbox checked={showCurve} onChange={e => setShowCurve(e.target.checked)}>Show Graphs</Checkbox>
        </Space>
      </Card>

      <EligibilityAlert result={eligibility} />

      <ErrorDisplay error={analysisError} />

      <Button type="primary" icon={<PlayCircleOutlined />} onClick={runAnalysis} loading={loading} size="large">
        Run Analysis
      </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><Text style={{ marginLeft: 12 }}>Running analysis...</Text></div></Card>}

      {results && !loading && (
        <>
          {kmGraph && showCurve && (
            <ErrorBoundary>
              <Card title="Survival Curves" style={{ marginTop: 16, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}>
                <Plot data={kmGraph.data} layout={kmGraph.layout} config={{ ...plotlyConfig, responsive: true }}
                  useResizeHandler style={{ width: '100%', height: 450 }} />
              </Card>
            </ErrorBoundary>
          )}
          {renderCoxGraphs()}
          <Card title="Results" style={{ marginTop: 16, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}
            extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
            {renderResults()}
            {renderInterpretation()}
          </Card>
          {activeTab === 'cox' && showCurve && (
            <Card title="Adjusted Survival Curves" style={{ marginTop: 16, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}
              extra={<Text type="secondary" style={{ fontSize: 11 }}>Cox model; blank = mean/reference</Text>}>
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <Space>
                  <Text>Primary exposure:</Text>
                  <Select style={{ width: 220 }} placeholder="Select exposure"
                    value={adjustedExposure}
                    onChange={(v) => { setAdjustedExposure(v); setAdjustedExposure2(undefined); setAdjusterValues({}) }}
                    options={covariates.map(c => ({ label: c, value: c }))} />
                  <Text>Second exposure:</Text>
                  <Select style={{ width: 220 }} placeholder="Optional" allowClear
                    value={adjustedExposure2} onChange={setAdjustedExposure2}
                    options={covariates.filter(c => c !== adjustedExposure).map(c => ({ label: c, value: c }))} />
                  <Button type="primary" onClick={handleAdjustedSurvival} loading={adjustedLoading}>
                    Generate
                  </Button>
                </Space>
                {adjustedExposure && (() => {
                  const adjCols = covariates.filter(c => c !== adjustedExposure && c !== adjustedExposure2)
                  if (adjCols.length === 0) return null
                  return (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                      <Text type="secondary" style={{ fontSize: 12, minWidth: 120 }}>Override adjusters:</Text>
                      {adjCols.map(adj => (
                        <div key={adj} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Text style={{ fontSize: 12, minWidth: 60 }}>{adj}:</Text>
                          <Input size="small" style={{ width: 80 }} placeholder="mean"
                            value={adjusterValues[adj] || ''}
                            onChange={e => setAdjusterValues(p => ({ ...p, [adj]: e.target.value }))} />
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </Space>
              {adjustedGraph && (
                <div style={{ marginTop: 16 }}>
                  <Plot data={adjustedGraph.data} layout={adjustedGraph.layout} config={{ ...plotlyConfig, responsive: true }}
                    useResizeHandler style={{ width: '100%', height: 450 }} />
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export default SurvivalPage
