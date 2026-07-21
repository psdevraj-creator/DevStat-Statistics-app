import React, { useState, useEffect } from 'react'
import {
  Card, Button, Select, Space, Typography, Steps, Radio, Checkbox, Tag,
  Alert, message, Spin, Divider, Switch, Result, Input,
} from 'antd'
import {
  PlayCircleOutlined, BulbOutlined, CheckCircleOutlined,
  WarningOutlined, ArrowRightOutlined, ArrowLeftOutlined,
} from '@ant-design/icons'
import { api, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'
import { formatApiError } from '../utils/errors'

const { Text, Title, Paragraph } = Typography

// ── Types ─────────────────────────────────────────────────────────────

type Goal = 'compare_groups' | 'test_association' | 'correlation' | 'model_predict' | 'survival_analysis'
type VarType = 'continuous' | 'binary' | 'categorical' | 'ordinal' | 'survival_time' | 'event_indicator' | 'unknown'

interface Variable {
  column: string
  inferred_type: VarType
  override_type: VarType | null
}

interface Recommendation {
  test_id: string
  test_name: string
  is_fallback: boolean
  rationale: string
  assumptions: { name: string; passed: boolean | null; detail: string; warning: string | null }[]
  warnings: string[]
  analysis_payload: Record<string, any>
  analysis_endpoint: string
}

interface SuggestResponse {
  goal: Goal
  outcome_type: VarType
  predictor_type: VarType
  paired: boolean
  num_groups: number | null
  primary: Recommendation
  fallback: Recommendation | null
  warnings: string[]
}

// ── Goal definitions ──────────────────────────────────────────────────

const GOALS: { value: Goal; label: string; desc: string }[] = [
  { value: 'compare_groups', label: 'Compare groups', desc: 'Compare a numeric outcome across two or more groups' },
  { value: 'test_association', label: 'Test association', desc: 'Test if two categorical variables are related' },
  { value: 'correlation', label: 'Correlation', desc: 'Measure the strength of relationship between numeric variables' },
  { value: 'model_predict', label: 'Model / predict an outcome', desc: 'Build a regression model to predict an outcome' },
  { value: 'survival_analysis', label: 'Analyze time-to-event data', desc: 'Survival analysis with time and event variables' },
]

const VAR_TYPES: { value: VarType; label: string }[] = [
  { value: 'continuous', label: 'Continuous' },
  { value: 'binary', label: 'Binary' },
  { value: 'categorical', label: 'Categorical' },
  { value: 'ordinal', label: 'Ordinal' },
  { value: 'survival_time', label: 'Survival time' },
  { value: 'event_indicator', label: 'Event indicator' },
]

// ── Component ─────────────────────────────────────────────────────────

const TestSuggestionPage: React.FC = () => {
  const [step, setStep] = useState(0)
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  // Wizard state
  const [goal, setGoal] = useState<Goal | null>(null)
  const [outcomeVar, setOutcomeVar] = useState<string | undefined>()
  const [predictorVars, setPredictorVars] = useState<string[]>([])
  const [groupVar, setGroupVar] = useState<string | undefined>()
  const [timeVar, setTimeVar] = useState<string | undefined>()
  const [eventVar, setEventVar] = useState<string | undefined>()
  const [paired, setPaired] = useState(false)
  const [numGroups, setNumGroups] = useState<number>(2)
  const [variables, setVariables] = useState<Variable[]>([])
  const [recommendation, setRecommendation] = useState<SuggestResponse | null>(null)
  const [runningTest, setRunningTest] = useState(false)
  const [manualTestId, setManualTestId] = useState<string | null>(null)
  const [overrideReason, setOverrideReason] = useState('')
  const [validationResult, setValidationResult] = useState<any>(null)
  const [availableTests, setAvailableTests] = useState<any[]>([])

  useEffect(() => { loadDatasets() }, [])
  useEffect(() => { api.get('/api/analysis/available-tests').then(r => setAvailableTests(Object.entries(r.data.tests || {}).map(([k,v]:[string,any]) => ({...v, test_id: k})))) }, [])
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
    try { const res = await datasetApi.columns(selectedDataset); setColumns(res.data || []) } catch { message.warning('Failed to load columns') }
  }

  // ── Build variable type list ────────────────────────────────────────
  useEffect(() => {
    const allVars = new Set<string>()
    if (outcomeVar) allVars.add(outcomeVar)
    predictorVars.forEach(v => allVars.add(v))
    if (groupVar) allVars.add(groupVar)
    if (timeVar) allVars.add(timeVar)
    if (eventVar) allVars.add(eventVar)

    setVariables(prev => {
      const map = new Map(prev.map(v => [v.column, v]))
      const next: Variable[] = []
      allVars.forEach(col => {
        const existing = map.get(col)
        next.push(existing || { column: col, inferred_type: 'unknown', override_type: null })
      })
      return next
    })
  }, [outcomeVar, predictorVars, groupVar, timeVar, eventVar])

  // ── Navigation ──────────────────────────────────────────────────────
  const canNext = (): boolean => {
    if (step === 0) return goal !== null
    if (step === 1) return !!selectedDataset && (
      (goal === 'compare_groups' && !!outcomeVar && !!groupVar && numGroups >= 2) ||
      (goal === 'test_association' && !!outcomeVar && !!groupVar) ||
      (goal === 'correlation' && predictorVars.length >= 2) ||
      (goal === 'model_predict' && !!outcomeVar && predictorVars.length >= 1) ||
      (goal === 'survival_analysis' && !!timeVar && !!eventVar)
    )
    if (step === 2) return true  // variable types always confirmable
    if (step === 3) return true  // design always confirmable
    return true
  }

  // ── Get recommendation ──────────────────────────────────────────────
  const getRecommendation = async () => {
    if (!selectedDataset) { message.warning('Select a dataset first'); return }
    setLoading(true)
    try {
      const res = await api.post('/api/analysis/suggest-test', {
        goal,
        outcome_variable: outcomeVar || null,
        predictor_variables: predictorVars,
        group_variable: groupVar || null,
        time_variable: timeVar || null,
        event_variable: eventVar || null,
        paired,
        num_groups: numGroups,
        variables: variables.map(v => ({
          column: v.column,
          inferred_type: v.inferred_type,
          override_type: v.override_type,
        })),
      })
      setRecommendation(res.data)
      setStep(4)
    } catch (err: any) {
      message.error(formatApiError(err, 'Recommendation failed'))
    } finally { setLoading(false) }
  }

  // ── Run recommended test ────────────────────────────────────────────
  const validateManualChoice = async (testId: string): Promise<{ allowed: boolean; tier: string }> => {
    try {
      const res = await api.post('/api/analysis/validate-test', {
        test_id: testId,
        outcome_variable: outcomeVar || null,
        group_variable: groupVar || null,
        predictor_variables: predictorVars,
        time_variable: timeVar || null,
        event_variable: eventVar || null,
        outcome_type: variables.find(v => v.column === outcomeVar)?.override_type || variables.find(v => v.column === outcomeVar)?.inferred_type || 'unknown',
        group_type: variables.find(v => v.column === groupVar)?.override_type || variables.find(v => v.column === groupVar)?.inferred_type || 'unknown',
        paired,
        num_groups: numGroups,
        override_reason: overrideReason || undefined,
      })
      setValidationResult(res.data)
      if (res.data.tier === 'hard') {
        message.error(res.data.message)
        return { allowed: false, tier: 'hard' }
      }
      if (res.data.tier === 'interrupt') {
        if (!overrideReason) {
          message.warning('Please provide a reason for overriding the recommendation.')
          return { allowed: false, tier: 'interrupt' }
        }
        message.info('Override accepted with reason: ' + overrideReason)
      }
      if (res.data.tier === 'soft') {
        message.warning(res.data.message)
      }
      return { allowed: true, tier: res.data.tier }
    } catch (err: any) {
      message.error(formatApiError(err, 'Validation failed'))
      return { allowed: false, tier: 'hard' }
    }
  }

  const runRecommendedTest = async (rec: Recommendation) => {
    setRunningTest(true)
    try {
      const res = await api.post(rec.analysis_endpoint, rec.analysis_payload)
      outputStore.addEntry('analysis', rec.test_name, res.data)
      message.success(`${rec.test_name} completed`)
    } catch (err: any) {
      message.error(formatApiError(err, `${rec.test_name} failed`))
    } finally { setRunningTest(false) }
  }

  // ── Renderers ───────────────────────────────────────────────────────

  const renderGoalStep = () => (
    <div>
      <Title level={5}>What do you want to do?</Title>
      <Paragraph type="secondary">Choose the analysis goal that matches your research question.</Paragraph>
      <Radio.Group value={goal} onChange={e => setGoal(e.target.value)} style={{ width: '100%' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          {GOALS.map(g => (
            <Card
              key={g.value}
              size="small"
              hoverable
              style={{ border: goal === g.value ? '2px solid #005eb8' : undefined, cursor: 'pointer' }}
              onClick={() => setGoal(g.value)}
            >
              <Radio value={g.value}><Text strong>{g.label}</Text></Radio>
              <br /><Text type="secondary" style={{ fontSize: 12 }}>{g.desc}</Text>
            </Card>
          ))}
        </Space>
      </Radio.Group>
    </div>
  )

  const renderVariableStep = () => (
    <div>
      <Title level={5}>Select variables</Title>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Space><Text style={{ width: 120 }}>Dataset:</Text>
          <Select style={{ width: 300 }} placeholder="Select dataset" value={selectedDataset || undefined}
            onChange={(v: string) => { setSelectedDataset(v); setOutcomeVar(undefined); setPredictorVars([]); setGroupVar(undefined); setTimeVar(undefined); setEventVar(undefined) }}
            options={datasets.map(d => ({ label: d.filename || d.name || d.id, value: d.id }))} />
        </Space>

        {goal === 'compare_groups' && (
          <>
            <Space><Text style={{ width: 120 }}>Outcome:</Text>
              <Select style={{ width: 300 }} placeholder="Continuous outcome" value={outcomeVar} onChange={setOutcomeVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Group:</Text>
              <Select style={{ width: 300 }} placeholder="Grouping variable" value={groupVar} onChange={setGroupVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}># Groups:</Text>
              <Select style={{ width: 100 }} value={numGroups} onChange={setNumGroups}
                options={[2,3,4,5,6,7,8,9,10].map(n => ({ label: String(n), value: n }))} /></Space>
            <Space><Text style={{ width: 120 }}>Paired:</Text><Switch checked={paired} onChange={setPaired} /></Space>
          </>
        )}

        {goal === 'test_association' && (
          <>
            <Space><Text style={{ width: 120 }}>Row variable:</Text>
              <Select style={{ width: 300 }} placeholder="Categorical" value={outcomeVar} onChange={setOutcomeVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Column variable:</Text>
              <Select style={{ width: 300 }} placeholder="Categorical" value={groupVar} onChange={setGroupVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </>
        )}

        {goal === 'correlation' && (
          <Space><Text style={{ width: 120 }}>Variables:</Text>
            <Select mode="multiple" style={{ width: 400 }} placeholder="Select 2+ variables" value={predictorVars} onChange={setPredictorVars}
              options={columns.map(c => ({ label: c, value: c }))} /></Space>
        )}

        {goal === 'model_predict' && (
          <>
            <Space><Text style={{ width: 120 }}>Outcome:</Text>
              <Select style={{ width: 300 }} placeholder="Dependent variable" value={outcomeVar} onChange={setOutcomeVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Predictors:</Text>
              <Select mode="multiple" style={{ width: 400 }} placeholder="Independent variables" value={predictorVars} onChange={setPredictorVars}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </>
        )}

        {goal === 'survival_analysis' && (
          <>
            <Space><Text style={{ width: 120 }}>Time:</Text>
              <Select style={{ width: 300 }} placeholder="Time-to-event" value={timeVar} onChange={setTimeVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Event:</Text>
              <Select style={{ width: 300 }} placeholder="Event indicator" value={eventVar} onChange={setEventVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
            <Space><Text style={{ width: 120 }}>Group (optional):</Text>
              <Select style={{ width: 300 }} placeholder="Optional grouping" allowClear value={groupVar} onChange={setGroupVar}
                options={columns.map(c => ({ label: c, value: c }))} /></Space>
          </>
        )}
      </Space>
    </div>
  )

  const renderTypeStep = () => (
    <div>
      <Title level={5}>Confirm variable types</Title>
      <Paragraph type="secondary">Types are inferred automatically. Override any that look wrong.</Paragraph>
      {variables.length === 0 && <Alert type="warning" message="No variables selected yet. Go back and select variables." />}
      <Space direction="vertical" style={{ width: '100%' }}>
        {variables.map((v, i) => (
          <Card key={v.column} size="small">
            <Space>
              <Text strong>{v.column}</Text>
              <Tag color="blue">{v.inferred_type}</Tag>
              <Text type="secondary">→</Text>
              <Select size="small" style={{ width: 150 }}
                value={v.override_type || v.inferred_type}
                onChange={(val: VarType) => {
                  const next = [...variables]
                  next[i] = { ...next[i], override_type: val === v.inferred_type ? null : val }
                  setVariables(next)
                }}
                options={VAR_TYPES.map(t => ({ label: t.label, value: t.value }))} />
            </Space>
          </Card>
        ))}
      </Space>
    </div>
  )

  const renderDesignStep = () => (
    <div>
      <Title level={5}>Study design</Title>
      {goal === 'compare_groups' && (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Card size="small"><Text>Groups: <Tag>{numGroups}</Tag></Text></Card>
          <Card size="small" hoverable onClick={() => setPaired(!paired)} style={{ cursor: 'pointer', border: paired ? '2px solid #005eb8' : undefined }}>
            <Checkbox checked={paired} onChange={e => setPaired(e.target.checked)}>
              <Text strong>Paired / repeated measures</Text>
            </Checkbox>
            <br /><Text type="secondary" style={{ fontSize: 12 }}>Check if the same subjects were measured under different conditions.</Text>
          </Card>
        </Space>
      )}
      {goal !== 'compare_groups' && (
        <Alert type="info" message="No additional design questions needed for this analysis goal." />
      )}
    </div>
  )

  const renderRecommendation = () => {
    if (!recommendation) return <Spin />
    const { primary, fallback } = recommendation

    return (
      <div>
        <Title level={5}><BulbOutlined /> Recommendation</Title>

        {/* Primary */}
        <Card style={{ borderLeft: '4px solid #005eb8', marginBottom: 16 }}>
          <Title level={5} style={{ color: '#005eb8' }}>{primary.test_name}</Title>
          <Paragraph>{primary.rationale}</Paragraph>

          {primary.warnings.length > 0 && (
            <Alert type="warning" message="Warnings" description={primary.warnings.map((w,i) => <div key={i}>• {w}</div>)} style={{ marginBottom: 12 }} />
          )}

          {primary.assumptions.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Text strong>Assumption checks:</Text>
              {primary.assumptions.map((a, i) => (
                <div key={i} style={{ marginLeft: 8 }}>
                  {a.passed === true ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                   a.passed === false ? <WarningOutlined style={{ color: '#faad14' }} /> :
                   <Text type="secondary">?</Text>}
                  <Text style={{ marginLeft: 4 }}>{a.name}: {a.detail}</Text>
                  {a.warning && <div><Text type="warning" style={{ fontSize: 11 }}>{a.warning}</Text></div>}
                </div>
              ))}
            </div>
          )}

          <Button type="primary" icon={<PlayCircleOutlined />} loading={runningTest}
            onClick={() => runRecommendedTest(primary)}>
            Run {primary.test_name}
          </Button>
        </Card>

        {/* Fallback */}
        {fallback && (
          <Card style={{ borderLeft: '4px solid #faad14' }}>
            <Title level={5} style={{ color: '#faad14' }}>Fallback: {fallback.test_name}</Title>
            <Paragraph>{fallback.rationale}</Paragraph>
            <Button icon={<PlayCircleOutlined />} loading={runningTest}
              onClick={() => runRecommendedTest(fallback)}>
              Run {fallback.test_name}
            </Button>
          </Card>
        )}

        {/* Warnings */}
        {recommendation.warnings.length > 0 && (
          <Alert type="info" style={{ marginTop: 16 }}
            message="Notes"
            description={recommendation.warnings.map((w, i) => <div key={i}>• {w}</div>)} />
        )}

        {/* Override: choose a different test */}
        <Divider />
        <Title level={5}>Choose a different test</Title>
        <Paragraph type="secondary">If you prefer a different test, select one below. DevStat will validate your choice.</Paragraph>
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          <Select
            style={{ width: '100%' }}
            placeholder="Select an alternative test..."
            value={manualTestId}
            onChange={async (val: string) => {
              setManualTestId(val)
              setOverrideReason('')
              if (val) await validateManualChoice(val)
            }}
            options={availableTests.map((t: any) => ({ label: t.name || t.test_id, value: t.test_id }))}
          />

          {/* Validation result */}
          {validationResult && manualTestId && (
            <>
              {validationResult.tier === 'hard' && (
                <Alert type="error" message="Cannot run this test" description={validationResult.message} showIcon />
              )}
              {validationResult.tier === 'interrupt' && (
                <>
                  <Alert type="warning" message="Design mismatch" description={validationResult.message} showIcon />
                  <Input.TextArea
                    rows={2}
                    placeholder="Explain why you are choosing this test despite the warning..."
                    value={overrideReason}
                    onChange={e => setOverrideReason(e.target.value)}
                  />
                  <Button
                    type="primary"
                    danger
                    onClick={async () => {
                      const result = await validateManualChoice(manualTestId!)
                      if (result.allowed) {
                        const test = availableTests.find((t: any) => t.test_id === manualTestId)
                        if (test) {
                          await api.post(test.endpoint, test.analysis_payload || recommendation?.primary.analysis_payload || {})
                          message.success(`${test.name} completed (with override)`)
                        }
                      }
                    }}
                  >
                    Run anyway (with override reason)
                  </Button>
                </>
              )}
              {validationResult.tier === 'soft' && (
                <>
                  <Alert type="info" message="Suboptimal choice" description={validationResult.message} showIcon />
                  <Button
                    onClick={async () => {
                      const test = availableTests.find((t: any) => t.test_id === manualTestId)
                      if (test) {
                        await api.post(test.endpoint, test.analysis_payload || recommendation?.primary.analysis_payload || {})
                        message.success(`${test.name} completed`)
                      }
                    }}
                  >
                    Continue anyway
                  </Button>
                </>
              )}
              {validationResult.tier === 'compatible' && (
                <>
                  <Alert type="success" message="Compatible choice" description="This test is compatible with your data." showIcon />
                  <Button
                    type="primary"
                    onClick={async () => {
                      const test = availableTests.find((t: any) => t.test_id === manualTestId)
                      if (test) {
                        await api.post(test.endpoint, recommendation?.primary.analysis_payload || {})
                        message.success(`${test.name} completed`)
                      }
                    }}
                  >
                    Run {availableTests.find((t: any) => t.test_id === manualTestId)?.name || manualTestId}
                  </Button>
                </>
              )}
            </>
          )}
        </Space>

        {/* Already-run feedback */}
        {runningTest && <div style={{ textAlign: 'center', marginTop: 16 }}><Spin /><Text style={{ marginLeft: 8 }}>Running analysis...</Text></div>}
      </div>
    )
  }

  // ── Step definitions ────────────────────────────────────────────────

  const steps = [
    { title: 'Goal', content: renderGoalStep() },
    { title: 'Variables', content: renderVariableStep() },
    { title: 'Types', content: renderTypeStep() },
    { title: 'Design', content: renderDesignStep() },
    { title: 'Recommendation', content: recommendation ? renderRecommendation() : <Spin tip="Getting recommendation..." /> },
  ]

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
      <Title level={4} style={{ color: '#1a1a2e' }}>Suggest Statistical Test</Title>
      <Paragraph type="secondary">
        Answer a few questions about your data and research goal. DevStat will recommend the right statistical test.
      </Paragraph>

      <Steps current={step} size="small" style={{ marginBottom: 24 }}>
        {steps.map((s, i) => <Steps.Step key={i} title={s.title} />)}
      </Steps>

      <Card>{steps[step].content}</Card>

      <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Button disabled={step === 0} onClick={() => setStep(step - 1)} icon={<ArrowLeftOutlined />}>Back</Button>
        <Space>
          {step === 3 && (
            <Button type="primary" onClick={getRecommendation} loading={loading} icon={<BulbOutlined />}>
              Get Recommendation
            </Button>
          )}
          {step < 3 && (
            <Button type="primary" onClick={() => setStep(step + 1)} disabled={!canNext()} icon={<ArrowRightOutlined />}>
              Next
            </Button>
          )}
          {step === 4 && (
            <Button onClick={() => { setStep(0); setRecommendation(null) }}>Start Over</Button>
          )}
        </Space>
      </div>
    </div>
  )
}

export default TestSuggestionPage
