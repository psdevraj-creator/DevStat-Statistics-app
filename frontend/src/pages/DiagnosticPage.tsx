import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, Input, Space, Typography, message, Spin, Table, Alert, Row, Col, Statistic,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import EligibilityAlert from '../components/EligibilityAlert'
import { useEligibilityCheck } from '../hooks/useEligibility'
import { diagnosticApi, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const DiagnosticPage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [testVar, setTestVar] = useState<string | undefined>(undefined)
  const [goldVar, setGoldVar] = useState<string | undefined>(undefined)
  const [positiveCode, setPositiveCode] = useState<string>('1')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  const eligParams = useMemo(() => ({
    analysis: 'logistic_regression',
    var_types: { dependent: 'binary' },
  }), [])
  const eligibility = useEligibilityCheck(testVar && goldVar ? eligParams : null)

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

  const runDiagnostic = async () => {
    if (!selectedDataset || !testVar || !goldVar) {
      message.warning('Please fill in all required fields')
      return
    }
    setLoading(true)
    try {
      const res = await diagnosticApi.run(selectedDataset, testVar, goldVar, positiveCode)
      setResults(res.data)
      outputStore.addEntry('diagnostic', 'Diagnostic test: ' + testVar + ' vs ' + goldVar, res.data)
      message.success('Analysis complete')
    } catch (err: any) {
      message.error('Analysis failed: ' + (err?.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  const renderContingencyTable = () => {
    if (!results) return null
    const raw = results.table || results.contingency_table || results.confusion_matrix || results['2x2']
    if (!raw) return null
    // R returns confusion_matrix as dict {tp, fp, fn, tn}; convert to array
    let table: any[]
    if (Array.isArray(raw)) {
      table = raw
    } else if (raw.tp !== undefined) {
      table = [
        { '': 'Test \u2193 / Gold \u2192', 'Gold+': 'Gold+', 'Gold-': 'Gold-' },
        { '': 'Test+', 'Gold+': raw.tp, 'Gold-': raw.fp },
        { '': 'Test-', 'Gold+': raw.fn, 'Gold-': raw.tn },
      ]
    } else {
      return null
    }
    
    const cols = Object.keys(table[0] || {}).map(key => ({
      title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      dataIndex: key, key,
      render: (v: any) => v !== null && v !== undefined ? String(v) : '-',
    }))
    return (
      <div style={{ marginBottom: 24 }}>
        <Text strong style={{ fontSize: 14 }}>2x2 Contingency Table</Text>
        <Table dataSource={table} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered style={{ marginTop: 8, maxWidth: 400 }} />
      </div>
    )
  }

  const renderMetrics = () => {
    if (!results) return null
    const data = results.metrics || results.statistics || results

    const metrics = [
      { label: 'Sensitivity', value: data.sensitivity ?? data.sens },
      { label: 'Specificity', value: data.specificity ?? data.spec },
      { label: 'PPV', value: data.ppv ?? data.positive_predictive_value },
      { label: 'NPV', value: data.npv ?? data.negative_predictive_value },
      { label: 'LR+', value: data.lr_plus ?? data.positive_likelihood_ratio },
      { label: 'LR-', value: data.lr_minus ?? data.negative_likelihood_ratio },
      { label: 'Accuracy', value: data.accuracy ?? data.acc },
      { label: 'AUC', value: data.auc ?? data.roc_auc },
    ].filter(m => m.value !== undefined && m.value !== null)

    if (metrics.length === 0) return null

    return (
      <Row gutter={[16, 16]}>
        {metrics.map(m => (
          <Col key={m.label} xs={12} sm={8} md={6}>
            <Card size="small" bodyStyle={{ textAlign: 'center', padding: '16px 12px' }}>
              <Statistic
                title={<Text style={{ fontSize: 12, color: '#64748b' }}>{m.label}</Text>}
                value={typeof m.value === 'number' ? (m.value * 100 > 10 ? (m.value * 100).toFixed(1) + '%' : m.value.toFixed(3)) : String(m.value)}
                valueStyle={{ color: '#005eb8', fontSize: 22, fontWeight: 600 }}
              />
            </Card>
          </Col>
        ))}
      </Row>
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

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Diagnostic Test Analysis</Title>

      <Card title="Configuration" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space><Text style={{ width: 140 }}>Dataset:</Text><Select style={{ width: 300 }} placeholder="Select dataset" value={selectedDataset || undefined} onChange={setSelectedDataset} options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))} /></Space>
          <Space><Text style={{ width: 140 }}>Test variable:</Text><Select style={{ width: 300 }} placeholder="Select test/diagnostic variable" value={testVar} onChange={setTestVar} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          <Space><Text style={{ width: 140 }}>Gold standard:</Text><Select style={{ width: 300 }} placeholder="Select gold standard variable" value={goldVar} onChange={setGoldVar} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          <Space><Text style={{ width: 140 }}>Positive code:</Text><Input style={{ width: 200 }} placeholder="e.g., 1, Yes, Positive" value={positiveCode} onChange={e => setPositiveCode(e.target.value)} /></Space>
        </Space>
      </Card>

      <EligibilityAlert result={eligibility} />

      <Button type="primary" icon={<PlayCircleOutlined />} onClick={runDiagnostic} loading={loading} size="large">
        Run Analysis
      </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><Text style={{ marginLeft: 12 }}>Running analysis...</Text></div></Card>}

      {results && !loading && (
        <Card title="Results" style={{ marginTop: 16 }} extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
          {renderContingencyTable()}
          {renderMetrics()}
          {renderInterpretation()}
        </Card>
      )}
    </div>
  )
}

export default DiagnosticPage
