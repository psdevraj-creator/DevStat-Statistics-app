import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, Checkbox, Tabs, Space, Typography, message, Spin, Table, Divider, Alert, Radio,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import EligibilityAlert from '../components/EligibilityAlert'
import BlockedAnalysisPanel from '../components/BlockedAnalysisPanel'
import { useEligibilityCheck } from '../hooks/useEligibility'
import { compareApi, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'
import { formatApiError } from '../utils/errors'

const { Text, Title } = Typography

const TEST_TYPES = [
  { label: 'Independent t-test', value: 'independent_ttest' },
  { label: 'Paired t-test', value: 'paired_ttest' },
  { label: 'Mann-Whitney U', value: 'mann_whitney' },
  { label: 'Wilcoxon Signed-Rank', value: 'wilcoxon' },
  { label: 'One-way ANOVA', value: 'anova' },
  { label: 'Kruskal-Wallis', value: 'kruskal_wallis' },
  { label: 'Chi-square', value: 'chi_square' },
]

const ComparePage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [testType, setTestType] = useState<string>('independent_ttest')
  const [groupVar, setGroupVar] = useState<string | undefined>(undefined)
  const [testVar, setTestVar] = useState<string | undefined>(undefined)
  const [testVar2, setTestVar2] = useState<string | undefined>(undefined)
  const [pairedVar1, setPairedVar1] = useState<string | undefined>(undefined)
  const [pairedVar2, setPairedVar2] = useState<string | undefined>(undefined)
  const [anovaVars, setAnovaVars] = useState<string[]>([])
  const [ciLevel, setCiLevel] = useState<number>(95)
  const [effectSize, setEffectSize] = useState(true)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  // ── Eligibility ──
  const eligParams = useMemo(() => {
    const params: any = { analysis: '', var_types: {} }
    const depType = testVar ? 'continuous' : 'nominal'
    switch (testType) {
      case 'independent_ttest':
        params.analysis = 'ttest'
        params.n_groups = groupVar && columns.length ? 3 : 2
        params.var_types = { dependent: depType }
        break
      case 'paired_ttest':
        params.analysis = 'ttest_paired'
        params.var_types = { dependent: depType }
        params.is_paired = true
        break
      case 'mann_whitney':
        params.analysis = 'mannwhitney'
        params.n_groups = groupVar && columns.length ? 3 : 2
        break
      case 'wilcoxon':
        params.analysis = 'wilcoxon'
        params.is_paired = true
        break
      case 'anova':
        params.analysis = 'anova'
        params.n_groups = groupVar && columns.length ? 3 : 0
        params.var_types = { dependent: depType }
        break
      case 'kruskal_wallis':
        params.analysis = 'kruskal'
        params.n_groups = 3
        break
      case 'chi_square':
        params.analysis = 'chisquare'
        params.var_types = { dependent: 'nominal' }
        break
    }
    return params
  }, [testType, groupVar, testVar, columns])
  const eligibility = useEligibilityCheck(eligParams.analysis ? eligParams : null)

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

  const buildVariables = () => {
    if (testType === 'independent_ttest') {
      if (!groupVar || !testVar) return null
      return { test_type: 'independent', dependent: [testVar], group: groupVar }
    }
    if (testType === 'mann_whitney') {
      if (!groupVar || !testVar) return null
      return { dependent: testVar, group: groupVar }
    }
    if (testType === 'paired_ttest' || testType === 'wilcoxon') {
      if (!pairedVar1 || !pairedVar2) return null
      return { variable1: pairedVar1, variable2: pairedVar2 }
    }
    if (testType === 'anova') {
      if (!groupVar || anovaVars.length === 0) return null
      return { test_type: 'anova', dependent: anovaVars, group: groupVar }
    }
    if (testType === 'kruskal_wallis') {
      if (!groupVar || anovaVars.length === 0) return null
      return { dependent: anovaVars[0], group: groupVar }
    }
    if (testType === 'chi_square') {
      if (!pairedVar1 || !pairedVar2) return null
      return { row: pairedVar1, col: pairedVar2 }
    }
    return null
  }

  const runTest = async () => {
    if (!selectedDataset) { message.warning('Please select a dataset'); return }
    const variables = buildVariables()
    if (!variables) { message.warning('Please fill in all required variable fields'); return }

    setLoading(true)
    try {
      const res = await compareApi.runTest(selectedDataset, testType, variables, {
        ci_level: ciLevel / 100,
        effect_size: effectSize,
      })
      setResults(res.data)
      outputStore.addEntry('compare', TEST_TYPES.find(t => t.value === testType)?.label || testType, res.data)
      message.success('Test complete')
    } catch (err: any) {
      message.error(formatApiError(err, 'Test failed'))
    } finally {
      setLoading(false)
    }
  }

  const renderResults = () => {
    if (!results) return null
    const data = results.data || results.results || results
    // ── Blocked / not-eligible result → show the guidance panel ────────
    if (data && (data.blocked === true || data.eligible === false)) {
      return <BlockedAnalysisPanel result={data} />
    }

    if (Array.isArray(data)) {
      const safeData = data
      const tableColumns = safeData.length > 0 ? Object.keys(safeData[0] || {}).map(key => ({
        title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        dataIndex: key,
        key,
        render: (v: any) => v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-',
      })) : []
      return <Table dataSource={safeData} columns={tableColumns} rowKey={(_, i) => String(i)} pagination={false} size="small" bordered />
    }

    if (data.statistic !== undefined || data.test_statistic !== undefined) {
      const stat = data.statistic || data.test_statistic
      const p = data.p_value ?? data.p ?? 1.0
      const rows = [
        { metric: 'Test Statistic', value: typeof stat === 'number' ? stat.toFixed(4) : String(stat) },
        { metric: 'P-value', value: typeof p === 'number' ? p.toFixed(4) : String(p) },
        { metric: 'Significant', value: p < 0.05 ? 'Yes' : 'No' },
      ]
      if (data.effect_size ?? data.cohens_d) rows.push({ metric: 'Effect Size', value: typeof (data.effect_size ?? data.cohens_d) === 'number' ? Number(data.effect_size ?? data.cohens_d).toFixed(4) : String(data.effect_size ?? data.cohens_d) })
      if (data.confidence_interval ?? data.ci_95) {
        const ci = data.confidence_interval ?? data.ci_95
        rows.push({ metric: 'CI', value: Array.isArray(ci) ? `[${ci.join(', ')}]` : JSON.stringify(ci) })
      }
      if (data.df !== undefined) rows.push({ metric: 'DF', value: String(data.df) })

      return (
        <Table
          dataSource={rows}
          columns={[
            { title: 'Metric', dataIndex: 'metric', key: 'metric' },
            { title: 'Value', dataIndex: 'value', key: 'value' },
          ]}
          rowKey="metric"
          pagination={false}
          size="small"
          bordered
        />
      )
    }

    return <pre>{JSON.stringify(results, null, 2)}</pre>
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

  const renderVariableSelectors = () => {
    switch (testType) {
      case 'independent_ttest':
      case 'mann_whitney':
        return (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Space><Text style={{ width: 120 }}>Group variable:</Text><Select style={{ width: 250 }} placeholder="Select group" value={groupVar} onChange={setGroupVar} options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Outcome variable:</Text><Select style={{ width: 250 }} placeholder="Select outcome (what you measured)" value={testVar} onChange={setTestVar} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </Space>
        )
      case 'paired_ttest':
      case 'wilcoxon':
        return (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Space><Text style={{ width: 120 }}>Variable 1:</Text><Select style={{ width: 250 }} placeholder="Select first variable" value={pairedVar1} onChange={setPairedVar1} options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Variable 2:</Text><Select style={{ width: 250 }} placeholder="Select second variable" value={pairedVar2} onChange={setPairedVar2} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </Space>
        )
      case 'anova':
      case 'kruskal_wallis':
        return (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Space><Text style={{ width: 120 }}>Group variable:</Text><Select style={{ width: 250 }} placeholder="Select group" value={groupVar} onChange={setGroupVar} options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Outcome variables:</Text><Select mode="multiple" style={{ width: 350 }} placeholder="Select outcome variables" value={anovaVars} onChange={setAnovaVars} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </Space>
        )
      case 'chi_square':
        return (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Space><Text style={{ width: 120 }}>First category (row):</Text><Select style={{ width: 250 }} placeholder="Select first category" value={pairedVar1} onChange={setPairedVar1} options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Second category (column):</Text><Select style={{ width: 250 }} placeholder="Select second category" value={pairedVar2} onChange={setPairedVar2} options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </Space>
        )
      default: return null
    }
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Compare Groups / Hypothesis Tests</Title>

      <Card title="Test Configuration" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space><Text style={{ width: 120 }}>Dataset:</Text><Select style={{ width: 300 }} placeholder="Select dataset" value={selectedDataset || undefined} onChange={setSelectedDataset} options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))} /></Space>
          <Space><Text style={{ width: 120 }}>Test type:</Text><Select style={{ width: 300 }} value={testType} onChange={setTestType} options={TEST_TYPES} /></Space>
          <Divider />
          {renderVariableSelectors()}
          <Divider />
          <Space>
            <Text style={{ width: 120 }}>CI Level:</Text>
            <Select style={{ width: 120 }} value={ciLevel} onChange={setCiLevel} options={[{ label: '90%', value: 90 }, { label: '95%', value: 95 }, { label: '99%', value: 99 }]} />
            <Checkbox checked={effectSize} onChange={e => setEffectSize(e.target.checked)}>Show Effect Size</Checkbox>
          </Space>
        </Space>
      </Card>

      <EligibilityAlert result={eligibility} />

      <Button type="primary" icon={<PlayCircleOutlined />} onClick={runTest} loading={loading} size="large">
        Run Test
      </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><Text style={{ marginLeft: 12 }}>Running test...</Text></div></Card>}

      {results && !loading && (
        <Card title="Results" style={{ marginTop: 16 }} extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
          {renderResults()}
          {renderInterpretation()}
        </Card>
      )}
    </div>
  )
}

export default ComparePage
