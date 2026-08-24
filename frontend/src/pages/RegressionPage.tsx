import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, Tabs, Space, Typography, message, Spin, Table, Divider, Alert, Radio,
} from 'antd'
import { PlayCircleOutlined, DoubleRightOutlined, ArrowRightOutlined, ArrowLeftOutlined, DoubleLeftOutlined, FileTextOutlined } from '@ant-design/icons'
import EligibilityAlert from '../components/EligibilityAlert'
import BlockedAnalysisPanel from '../components/BlockedAnalysisPanel'
import { useEligibilityCheck } from '../hooks/useEligibility'
import { regressionApi, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'
import { formatApiError } from '../utils/errors'

const { Text, Title } = Typography

const METHODS = [
  { label: 'All at once (Enter)', value: 'enter' },
  { label: 'Automatic — stepwise', value: 'stepwise' },
  { label: 'Add one at a time (Forward)', value: 'forward' },
  { label: 'Remove one at a time (Backward)', value: 'backward' },
]

const RegressionPage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<string>('linear')
  const [dependent, setDependent] = useState<string | undefined>(undefined)
  const [availableVars, setAvailableVars] = useState<string[]>([])
  const [independents, setIndependents] = useState<string[]>([])
  const [method, setMethod] = useState<string>('enter')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  const eligParams = useMemo(() => ({
    analysis: activeTab === 'linear' ? 'linear_regression' : 'logistic_regression',
    var_types: { dependent: dependent ? 'continuous' : 'unknown' },
  }), [activeTab, dependent])
  const eligibility = useEligibilityCheck(dependent ? eligParams : null)

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
    try {
      const res = await datasetApi.columns(selectedDataset)
      const cols = res.data.columns || res.data || []
      setColumns(cols)
      setAvailableVars(cols)
      setDependent(undefined)
      setIndependents([])
    } catch { message.warning('Failed to load columns') }
  }

  const moveToIndependents = () => {
    setIndependents(prev => [...prev, ...availableVars])
    setAvailableVars([])
  }

  const moveFromIndependents = () => {
    setAvailableVars(prev => [...prev, ...independents])
    setIndependents([])
  }

  const addIndependent = (v: string) => {
    setIndependents(prev => [...prev, v])
    setAvailableVars(prev => prev.filter(x => x !== v))
  }

  const removeIndependent = (v: string) => {
    setAvailableVars(prev => [...prev, v])
    setIndependents(prev => prev.filter(x => x !== v))
  }

  const runRegression = async () => {
    if (!selectedDataset || !dependent || independents.length === 0) {
      message.warning('Please select dataset, dependent variable, and at least one independent variable')
      return
    }
    setLoading(true)
    try {
      const res = await regressionApi.run(selectedDataset, activeTab, dependent, independents, method)
      setResults(res.data)
      outputStore.addEntry('regression', activeTab + ' regression', res.data)
      message.success('Regression complete')
    } catch (err: any) {
      message.error(formatApiError(err, 'Regression failed'))
    } finally { setLoading(false) }
  }

  const renderModelSummary = () => {
    if (!results) return null
    const summary = results.model_fit || results.model_summary || results.summary
    if (!summary) return null
    const rows = Array.isArray(summary) ? summary : [summary]
    const cols = Object.keys(rows[0] || {}).map(key => ({
      title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      dataIndex: key,
      key,
      render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-',
    }))
    return (
      <div style={{ marginBottom: 16 }}>
        <Text strong>Model Summary</Text>
        <Table dataSource={rows} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered style={{ marginTop: 8 }} />
      </div>
    )
  }

  const renderANOVA = () => {
    const anova = results.anova || results.anova_table
    if (!anova) return null
    const rows = Array.isArray(anova) ? anova : [anova]
    const cols = Object.keys(rows[0] || {}).map(key => ({
      title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      dataIndex: key,
      key,
      render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-',
    }))
    return (
      <div style={{ marginBottom: 16 }}>
        <Text strong>ANOVA</Text>
        <Table dataSource={rows} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered style={{ marginTop: 8 }} />
      </div>
    )
  }

  const renderCoefficients = () => {
    const coeffs = results.coefficients || results.coeffs
    if (!coeffs) return null
    const rows = Array.isArray(coeffs) ? coeffs : [coeffs]
    const cols = Object.keys(rows[0] || {}).map(key => ({
      title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      dataIndex: key,
      key,
      render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-',
    }))
    return (
      <div>
        <Text strong>Coefficients</Text>
        <Table dataSource={rows} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered style={{ marginTop: 8 }} />
      </div>
    )
  }

  const renderInterpretation = () => {
    if (!results) return null
    const interp = results.interpretation || results.summary_text
    if (!interp) return null
    return (
      <Alert type="info" message="Interpretation"
        description={typeof interp === 'string' ? interp : JSON.stringify(interp, null, 2)}
        style={{ marginTop: 16, background: '#f0f7ff', border: '1px solid #bae0ff' }} />
    )
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Regression Analysis</Title>

      <Alert type="info" showIcon message="Mixed models coming soon" description="Linear and generalized linear mixed models are not yet available in the Python engine. Use linear or logistic regression instead." style={{ marginBottom: 16 }} closable />

      <Card title="Configuration" style={{ marginBottom: 16 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          { key: 'linear', label: 'Linear Regression' },
          { key: 'logistic', label: 'Logistic Regression' },
        ]} />

        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space><Text style={{ width: 140 }}>Dataset:</Text><Select style={{ width: 300 }} placeholder="Select dataset" value={selectedDataset || undefined} onChange={setSelectedDataset} options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))} /></Space>
          <Space><Text style={{ width: 140 }}>Dependent variable:</Text><Select style={{ width: 300 }} placeholder="Select dependent" value={dependent} onChange={setDependent} options={columns.map(c => ({ label: c, value: c }))} /></Space>

          <Divider />
          <Text strong>Independent Variables</Text>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <Text style={{ fontSize: 12, color: '#64748b' }}>Available</Text>
              <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, minHeight: 160, maxHeight: 250, overflow: 'auto', padding: 4, marginTop: 4 }}>
                {availableVars.map(v => (
                  <div key={v} onClick={() => addIndependent(v)} style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: 4, margin: 2, fontSize: 13 }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#e8f0fe')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>{v}</div>
                ))}
              </div>
            </div>
            <Space direction="vertical" size={4}>
              <Button icon={<DoubleRightOutlined />} onClick={moveToIndependents} size="small" />
              <Button icon={<ArrowRightOutlined />} onClick={() => availableVars.length > 0 && addIndependent(availableVars[0])} size="small" />
              <Button icon={<ArrowLeftOutlined />} onClick={() => independents.length > 0 && removeIndependent(independents[independents.length - 1])} size="small" />
              <Button icon={<DoubleLeftOutlined />} onClick={moveFromIndependents} size="small" />
            </Space>
            <div style={{ flex: 1 }}>
              <Text style={{ fontSize: 12, color: '#64748b' }}>Selected</Text>
              <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, minHeight: 160, maxHeight: 250, overflow: 'auto', padding: 4, marginTop: 4 }}>
                {independents.map(v => (
                  <div key={v} onClick={() => removeIndependent(v)} style={{ padding: '6px 12px', cursor: 'pointer', borderRadius: 4, margin: 2, fontSize: 13, background: '#e8f0fe' }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#d0e2f7')}
                    onMouseLeave={e => (e.currentTarget.style.background = '#e8f0fe')}>{v}</div>
                ))}
              </div>
            </div>
          </div>

          <Divider />
          <Space><Text style={{ width: 140 }}>Method:</Text><Select style={{ width: 200 }} value={method} onChange={setMethod} options={METHODS} /></Space>
        </Space>
      </Card>

        <EligibilityAlert result={eligibility} />

        <Button type="primary" icon={<PlayCircleOutlined />} onClick={runRegression} loading={loading} size="large">
          Run Regression
        </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><Text style={{ marginLeft: 12 }}>Running regression...</Text></div></Card>}

      {results && !loading && (
        <Card title="Results" style={{ marginTop: 16 }} extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
          {(results.blocked === true || results.eligible === false)
            ? <BlockedAnalysisPanel result={results} />
            : (<>{renderModelSummary()}{renderANOVA()}{renderCoefficients()}{renderInterpretation()}</>)}
        </Card>
      )}
    </div>
  )
}

export default RegressionPage
