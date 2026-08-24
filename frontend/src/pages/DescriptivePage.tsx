import React, { useState, useEffect } from 'react'
import {
  Card, Button, Select, Checkbox, Tabs, Space, Typography, message, Spin, Tag, Table, Divider, Alert,
} from 'antd'
import { PlayCircleOutlined, ArrowLeftOutlined, ArrowRightOutlined, DoubleLeftOutlined, DoubleRightOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { descriptiveApi, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'
import ChartRenderer from '../components/ChartRenderer'
import ErrorBoundary from '../components/ErrorBoundary'
import BlockedAnalysisPanel from '../components/BlockedAnalysisPanel'

const { Text, Title } = Typography

const DESCRIPTIVE_OPTIONS = [
  { label: 'Mean', value: 'mean' },
  { label: 'Median', value: 'median' },
  { label: 'Std Deviation', value: 'std' },
  { label: 'Variance', value: 'variance' },
  { label: 'Minimum', value: 'min' },
  { label: 'Maximum', value: 'max' },
  { label: 'Range', value: 'range' },
  { label: 'Skewness', value: 'skewness' },
  { label: 'Kurtosis', value: 'kurtosis' },
  { label: 'Sum', value: 'sum' },
  { label: 'Count', value: 'count' },
]

const DescriptivePage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [availableVars, setAvailableVars] = useState<string[]>([])
  const [selectedVars, setSelectedVars] = useState<string[]>([])
  const [groupBy, setGroupBy] = useState<string | undefined>(undefined)
  const [descriptiveOptions, setDescriptiveOptions] = useState<string[]>(['mean', 'std', 'min', 'max', 'count'])
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<string>('descriptives')

  useEffect(() => {
    loadDatasets()
  }, [])

  useEffect(() => {
    if (selectedDataset) loadColumns()
  }, [selectedDataset])

  const loadDatasets = async () => {
    try {
      const res = await datasetApi.list()
      const ds = res.data || []
      setDatasets(ds)
      if (ds.length > 0 && !selectedDataset) setSelectedDataset(ds[0].id)
    } catch { message.warning('Failed to load datasets') }
  }

  const loadColumns = async () => {
    try {
      const res = await datasetApi.columns(selectedDataset)
      const cols = res.data.columns || res.data || []
      setColumns(cols)
      setAvailableVars(cols)
    } catch { message.warning('Failed to load columns') }
  }

  const moveToSelected = () => {
    const toMove = availableVars.filter(v => !selectedVars.includes(v))
    setSelectedVars(prev => [...prev, ...toMove])
    setAvailableVars([])
  }

  const moveFromSelected = () => {
    setAvailableVars(prev => [...prev, ...selectedVars])
    setSelectedVars([])
  }

  const moveItemToSelected = (item: string) => {
    setSelectedVars(prev => [...prev, item])
    setAvailableVars(prev => prev.filter(v => v !== item))
  }

  const moveItemFromSelected = (item: string) => {
    setAvailableVars(prev => [...prev, item])
    setSelectedVars(prev => prev.filter(v => v !== item))
  }

  const runAnalysis = async () => {
    if (!selectedDataset || selectedVars.length === 0) {
      message.warning('Please select a dataset and at least one variable')
      return
    }
    setLoading(true)
    try {
      let res
      if (activeTab === 'descriptives') {
        res = await descriptiveApi.descriptives(selectedDataset, selectedVars, 
          Object.fromEntries(descriptiveOptions.map(o => [o, true])), groupBy)
      } else if (activeTab === 'frequencies') {
        res = await descriptiveApi.frequencies(selectedDataset, selectedVars)
      } else if (activeTab === 'crosstabs') {
        if (selectedVars.length < 2) {
          message.warning('Please select at least 2 variables for crosstabs')
          setLoading(false)
          return
        }
        res = await descriptiveApi.crosstabs(selectedDataset, selectedVars[0], selectedVars[1])
      } else if (activeTab === 'explore') {
        if (selectedVars.length !== 1) {
          message.warning('Please select exactly 1 variable for Explore')
          setLoading(false)
          return
        }
        res = await descriptiveApi.explore(selectedVars[0])
      }
      setResults(res?.data || res)
      outputStore.addEntry('descriptive', activeTab + ' analysis', res?.data)
      message.success('Analysis complete')
    } catch (err: any) {
      message.error('Analysis failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const renderDescriptivesTable = () => {
    if (!results) return null

    // ── Blocked / not-eligible result → show the guidance panel ────────
    if (results.blocked === true || results.eligible === false) {
      return <BlockedAnalysisPanel result={results} />
    }

    // ── Crosstabs format: {row, col, table (2D array), chi2, ...} ──
    // Check first because crosstabs also have a `table` field (2D array, not {value,count} objects).
    if (results.chi2 != null || results.chi_square != null) {
      return (
        <ErrorBoundary>
          <ChartRenderer data={results} title={`Crosstab: ${results.row || ''} × ${results.col || ''}`} />
        </ErrorBoundary>
      )
    }

    // ── Frequencies format: {column, n, missing, table: [{value, count, percent, cumulative_percent}]} ──
    if (results.table && Array.isArray(results.table) && results.table[0]?.value !== undefined) {
      return (
        <>
          <div style={{ marginBottom: 16, fontSize: 13, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <span><Text strong>Column: </Text>{results.column || 'N/A'}</span>
            <span>|</span>
            <span><Text strong>Valid N: </Text>{results.n ?? 'N/A'}</span>
            <span>|</span>
            <span><Text strong>Missing: </Text>{results.missing ?? 'N/A'}</span>
            {results.table.length > 1 && (
              <span>|</span>
            )}
            {results.table.length > 1 && (
              <span><Text strong>Categories: </Text>{results.table.length}</span>
            )}
          </div>
          <ErrorBoundary>
            <ChartRenderer data={results} title={`Frequency: ${results.column || ''}`} />
          </ErrorBoundary>
        </>
      )
    }

    // ── Descriptives format: {_columns: [...], col_name: {stats...}} — transform to rows ──
    const cols = results._columns || []
    if (cols.length > 0) {
      const rows = cols.map((col: string) => {
        const stats = results[col] || {}
        return { name: col, ...stats }
      })
      const firstRow = rows[0] || {}
      const colKeys = Object.keys(firstRow)
      const tableColumns = colKeys.map(key => ({
        title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        dataIndex: key,
        key,
        render: (v: any) => v !== null && v !== undefined
          ? (typeof v === 'number' ? String(Number.isInteger(v) ? v : v.toFixed(3)) : String(v))
          : '-',
      }))
      return (
        <Table
          dataSource={rows}
          columns={tableColumns}
          rowKey="name"
          pagination={false}
          size="small"
          bordered
          scroll={{ x: 'max-content' }}
        />
      )
    }
    // Fallback: try other shapes
    const data = results.data || results.results || results.descriptives
    if (Array.isArray(data)) {
      const fallbackCols = Object.keys(data[0] || {}).map(key => ({
        title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        dataIndex: key,
        key,
        render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? String(Number.isInteger(v) ? v : v.toFixed(3)) : String(v)) : '-',
      }))
      return <Table dataSource={data} columns={fallbackCols} rowKey={(_, idx) => String(idx)} pagination={false} size="small" bordered />
    }
    // Last resort: unrecognized format
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
      <Alert
        type="info"
        message="Interpretation"
        description={typeof interp === 'string' ? interp : JSON.stringify(interp, null, 2)}
        style={{ marginTop: 16, background: '#f0f7ff', border: '1px solid #bae0ff' }}
      />
    )
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Descriptive Statistics</Title>

      <Card title="Variable Selection" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space>
            <Text>Dataset:</Text>
            <Select
              style={{ width: 300 }}
              placeholder="Select dataset"
              value={selectedDataset || undefined}
              onChange={setSelectedDataset}
              options={datasets.map((d: any) => ({
                label: d.filename || d.name || d.id,
                value: d.id,
              }))}
            />
          </Space>

          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <Text strong style={{ fontSize: 12, color: '#64748b' }}>Available Variables</Text>
              <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, minHeight: 200, maxHeight: 300, overflow: 'auto', padding: 4, marginTop: 4 }}>
                {availableVars.map(v => (
                  <div
                    key={v}
                    onClick={() => moveItemToSelected(v)}
                    style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: 4, margin: 2, fontSize: 13 }}
                    className="variable-item"
                  >
                    {v}
                  </div>
                ))}
              </div>
            </div>

            <Space direction="vertical" size={4}>
              <Button icon={<DoubleRightOutlined />} onClick={moveToSelected} size="small" title="Move all" />
              <Button icon={<ArrowRightOutlined />} onClick={() => selectedVars.length === 0 && availableVars.length > 0 && moveItemToSelected(availableVars[0])} size="small" title="Move selected" />
              <Button icon={<ArrowLeftOutlined />} onClick={() => selectedVars.length > 0 && moveItemFromSelected(selectedVars[selectedVars.length - 1])} size="small" title="Move back" />
              <Button icon={<DoubleLeftOutlined />} onClick={moveFromSelected} size="small" title="Remove all" />
            </Space>

            <div style={{ flex: 1 }}>
              <Text strong style={{ fontSize: 12, color: '#64748b' }}>Selected Variables</Text>
              <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, minHeight: 200, maxHeight: 300, overflow: 'auto', padding: 4, marginTop: 4 }}>
                {selectedVars.map(v => (
                  <div
                    key={v}
                    onClick={() => moveItemFromSelected(v)}
                    style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: 4, margin: 2, fontSize: 13, background: '#e8f0fe' }}
                    className="variable-item"
                  >
                    {v}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <Space>
            <Text>Group by:</Text>
            <Select
              style={{ width: 200 }}
              placeholder="None"
              allowClear
              value={groupBy}
              onChange={setGroupBy}
              options={columns.map(c => ({ label: c, value: c }))}
            />
          </Space>
        </Space>
      </Card>

      <Card title="Analysis Options" style={{ marginBottom: 16 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          {
            key: 'descriptives',
            label: 'Descriptives',
            children: (
              <div>
                <Text strong style={{ fontSize: 12, color: '#64748b', display: 'block', marginBottom: 8 }}>Statistics to compute:</Text>
                <Checkbox.Group
                  options={DESCRIPTIVE_OPTIONS}
                  value={descriptiveOptions}
                  onChange={setDescriptiveOptions as any}
                />
              </div>
            ),
          },
          {
            key: 'frequencies',
            label: 'Frequencies',
            children: <Text type="secondary">Generate frequency tables for selected variables.</Text>,
          },
          {
            key: 'crosstabs',
            label: 'Crosstabs',
            children: (
              <Text type="secondary">
                Cross-tabulation table. Select exactly 2 variables (first = row, second = column).
              </Text>
            ),
          },
          {
            key: 'explore',
            label: 'Explore',
            children: (
              <Text type="secondary">
                Normality tests, outlier detection, and distribution diagnostics. Select exactly 1 variable.
              </Text>
            ),
          },
        ]} />

        <Divider />
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={runAnalysis} loading={loading} size="large">
          Run Analysis
        </Button>
      </Card>

      {loading && (
        <Card><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><Text style={{ marginLeft: 12 }}>Running analysis...</Text></div></Card>
      )}

      {results && !loading && (
        <Card title="Results"
          extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
          {renderDescriptivesTable()}
          {renderInterpretation()}
        </Card>
      )}

      <style>{`
        .variable-item:hover { background: #e8f0fe; }
      `}</style>
    </div>
  )
}

export default DescriptivePage
