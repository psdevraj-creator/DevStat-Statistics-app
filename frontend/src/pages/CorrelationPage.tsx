import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, Space, Typography, message, Spin, Table, Alert, Tag,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import EligibilityAlert from '../components/EligibilityAlert'
import { useEligibilityCheck } from '../hooks/useEligibility'
import { correlationApi, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const METHODS = [
  { label: 'Pearson (linear)', value: 'pearson' },
  { label: 'Spearman (ranked / monotonic)', value: 'spearman' },
  { label: 'Kendall (robust, small samples)', value: 'kendall' },
]

const CorrelationPage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [variables, setVariables] = useState<string[]>([])
  const [method, setMethod] = useState<string>('pearson')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  const eligParams = useMemo(() => ({
    analysis: 'correlation',
    var_types: Object.fromEntries(variables.map(v => [v, 'continuous'])),
  }), [variables])
  const eligibility = useEligibilityCheck(variables.length >= 2 ? eligParams : null)

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

  const runCorrelation = async () => {
    if (!selectedDataset || variables.length < 2) {
      message.warning('Please select at least 2 variables')
      return
    }
    setLoading(true)
    try {
      const res = await correlationApi.run(selectedDataset, variables, method)
      setResults(res.data)
      outputStore.addEntry('correlation', method + ' correlation', res.data)
      message.success('Correlation complete')
    } catch (err: any) {
      message.error('Correlation failed: ' + (err?.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  const renderCorrelationMatrix = () => {
    if (!results) return null
    const data = results.matrix || results.correlation_matrix || results.data || results
    const pvalues = results.p_values || results.pvalues || {}

    // If we have a matrix in the form of correlation values
    if (Array.isArray(data)) {
      // Check if it's a flat table or a matrix
      if (data.length > 0 && (data[0].variable1 !== undefined || data[0].var1 !== undefined)) {
        // Flat format with variable1, variable2, correlation, p_value
        const cols = Object.keys(data[0] || {}).map(key => ({
          title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
          dataIndex: key, key,
          render: (v: any) => {
            if (v === null || v === undefined) return '-'
            if (typeof v === 'number') {
              if (['p', 'p_value', 'p-value', 'pval'].includes(key.toLowerCase())) {
                const isSig = v < 0.05
                const isHighSig = v < 0.01
                const isVHighSig = v < 0.001
                return (
                  <span>
                    {v.toFixed(4)}
                    {isSig && <Tag color={isVHighSig ? 'red' : isHighSig ? 'orange' : 'blue'} style={{ marginLeft: 4 }}>{isVHighSig ? '***' : isHighSig ? '**' : '*'}</Tag>}
                  </span>
                )
              }
              return v.toFixed(4)
            }
            return String(v)
          },
        }))
        return <Table dataSource={data} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered />
      }

      // Correlation matrix as 2D array or table format
      if (data.length > 0 && typeof data[0] === 'object') {
        const cols = Object.keys(data[0] || {}).map(key => ({
          title: key,
          dataIndex: key, key,
          render: (v: any) => {
            if (v === null || v === undefined) return '-'
            if (typeof v === 'number') return v.toFixed(4)
            return String(v)
          },
        }))
        return <Table dataSource={data} columns={cols} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered />
      }
    }

    // Try to render as raw
    return <pre>{JSON.stringify(results, null, 2)}</pre>
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
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Correlation Analysis</Title>

      <Card title="Configuration" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space><Text style={{ width: 120 }}>Dataset:</Text><Select style={{ width: 300 }} placeholder="Select dataset" value={selectedDataset || undefined} onChange={setSelectedDataset} options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))} /></Space>
          <Space><Text style={{ width: 120 }}>Variables:</Text><Select mode="multiple" style={{ width: 350 }} placeholder="Select 2+ variables" value={variables} onChange={setVariables} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          <Space><Text style={{ width: 120 }}>Method:</Text><Select style={{ width: 200 }} value={method} onChange={setMethod} options={METHODS} /></Space>
        </Space>
      </Card>

      <EligibilityAlert result={eligibility} />

      <Button type="primary" icon={<PlayCircleOutlined />} onClick={runCorrelation} loading={loading} size="large">
        Run Correlation
      </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><Text style={{ marginLeft: 12 }}>Running correlation...</Text></div></Card>}

      {results && !loading && (
        <Card title="Correlation Results" style={{ marginTop: 16 }} extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
            Method: {method.charAt(0).toUpperCase() + method.slice(1)} | Significance: * p&lt;0.05, ** p&lt;0.01, *** p&lt;0.001
          </Text>
          {renderCorrelationMatrix()}
          {renderInterpretation()}
        </Card>
      )}
    </div>
  )
}

export default CorrelationPage
