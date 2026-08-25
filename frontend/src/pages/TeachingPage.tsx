import React, { useEffect, useState } from 'react'
import { Card, Typography, Space, Radio, Button, Collapse, Tag, Spin, message, Table, Alert, Divider } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../stores/authStore'
import { authApi } from '../api/authApi'
import api, { setTeachingActive, pricingApi, gbp } from '../api/client'

const { Title, Paragraph, Text } = Typography

const PROGRESS_KEY = 'devstat_teach_progress'

interface Step {
  kind: 'info' | 'question' | 'run' | 'summary'
  title?: string
  body?: string
  prompt?: string
  options?: string[]
  correct?: number
  why_correct?: string
  why_wrong?: Record<string, string>
  hint?: string
  emoji?: string
  endpoint?: string
  payload?: Record<string, any>
  explain?: string
}

interface ScenarioCard { id: string; title: string; blurb: string; emoji: string; price_cents: number; free: boolean; steps?: number; owned?: boolean; licensed?: boolean }

function isScalar(v: any) { return v === null || ['string', 'number', 'boolean'].includes(typeof v) }

// Flatten a result into a readable list of label/value rows (scalar leaves only).
function flatten(data: any, prefix = ''): [string, any][] {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return []
  const rows: [string, any][] = []
  for (const [k, v] of Object.entries(data)) {
    const label = prefix ? `${prefix}.${k}` : k
    if (Array.isArray(v)) continue
    if (v && typeof v === 'object') {
      rows.push(...flatten(v, label))
    } else if (isScalar(v)) {
      rows.push([label, v])
    }
  }
  return rows
}

function fmt(v: any) {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : Number(v).toFixed(4)
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  return v == null ? '—' : String(v)
}

function RenderResult({ data }: { data: any }) {
  if (!data) return null
  const table = Array.isArray(data?.table) && data.table.length > 0 ? data.table : null
  const rows = flatten(data).filter(([k]) => k !== 'qa' && !k.startsWith('qa'))
  const colTitles = table ? (typeof table[0] === 'object' ? ['Statistic', 'Value'] : ['Value']) : []
  return (
    <div>
      {table ? (
        Array.isArray(table[0])
          ? <Table size="small" pagination={false} dataSource={table.map((r: any[], i: number) => ({ key: i, a: fmt(r[0]), b: fmt(r[1]) }))} columns={[{ title: 'Statistic', dataIndex: 'a', key: 'a' }, { title: 'Value', dataIndex: 'b', key: 'b' }]} />
          : <Table size="small" pagination={false} scroll={{ x: true }} dataSource={table.map((r: any, i: number) => ({ key: i, ...r }))} columns={Object.keys(table[0]).map((c) => ({ title: c, dataIndex: c, key: c, render: (v: any) => fmt(v) }))} />
      ) : (
        rows.length > 0 && (
          <Table size="small" pagination={false} rowKey={(r: any) => r.k} dataSource={rows.map(([k, v]: [string, any]) => ({ k, v: fmt(v) }))} columns={[{ title: 'Result', dataIndex: 'k', key: 'k' }, { title: 'Value', dataIndex: 'v', key: 'v' }]} />
        )
      )}
      <Collapse ghost items={[{ key: 'json', label: 'View full JSON', children: <pre style={{ fontSize: 12, overflow: 'auto', maxHeight: 320, background: '#f6f8fa', padding: 12, borderRadius: 6 }}>{JSON.stringify(data, null, 2)}</pre> }]} />
    </div>
  )
}

function loadProgress(): any | null {
  try { return JSON.parse(sessionStorage.getItem(PROGRESS_KEY) || 'null') } catch { return null }
}
function saveProgress(p: any) { try { sessionStorage.setItem(PROGRESS_KEY, JSON.stringify(p)) } catch {} }
function clearProgress() { try { sessionStorage.removeItem(PROGRESS_KEY) } catch {} }

const TeachingPage: React.FC = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [scenarios, setScenarios] = useState<ScenarioCard[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [stepIdx, setStepIdx] = useState(0)
  const [choice, setChoice] = useState<number | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [runResult, setRunResult] = useState<any>(null)
  const [running, setRunning] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const [teachPrice, setTeachPrice] = useState('£1')

  useEffect(() => { pricingApi.status().then((r) => setTeachPrice(gbp(r.data?.prices?.teaching ?? 100))).catch(() => {}) }, [])

  const loadList = () => api.get('/api/teaching/scenarios').then((r) => setScenarios(r.data.scenarios || [])).catch(() => {})
  useEffect(() => { loadList() }, [])
  useEffect(() => {
    if (location.search.includes('paid=1')) { loadList(); navigate('/teaching', { replace: true }) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search])

  useEffect(() => () => setTeachingActive(false), [])

  const loadLesson = async (sid: string, resumeAt = 0) => {
    setLoadingData(true); setTeachingActive(true)
    try {
      await api.post(`/api/teaching/scenarios/${sid}/load`)
      const full = await api.get(`/api/teaching/scenarios/${sid}`)
      setSelected({ ...full.data, stepsLoaded: true })
      setStepIdx(resumeAt); setChoice(null); setRevealed(false); setRunResult(null)
      if (resumeAt > 0) saveProgress({ sid, stepIdx: resumeAt, choice: null, revealed: false })
      message.success('Lesson started — dataset loaded.')
    } catch (e: any) {
      if (e?.response?.status === 401) { message.info('Please sign in for this case.'); navigate('/auth') }
      else if (e?.response?.status === 402) { message.warning('This case needs to be unlocked. Subscribe, then buy it for ' + teachPrice + '.'); if (!user) navigate('/auth') }
      else message.error(e?.response?.data?.detail || e?.message || 'Could not start the lesson.')
      setTeachingActive(false)
    } finally { setLoadingData(false) }
  }

  // Auto-resume the in-progress lesson after switching tabs.
  useEffect(() => {
    if (selected?.stepsLoaded) return
    const prog = loadProgress()
    if (prog && prog.sid && scenarios.some((s) => s.id === prog.sid)) {
      loadLesson(prog.sid, prog.stepIdx || 0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarios])

  const step: Step | undefined = selected?.steps?.[stepIdx]
  const isLast = selected && stepIdx === selected.steps.length - 1

  const persist = (idx: number, ch: number | null, rev: boolean) => {
    if (selected) saveProgress({ sid: selected.id, stepIdx: idx, choice: ch, revealed: rev })
  }

  const subscribeFirst = async () => {
    if (!user) { message.info('Please sign in first.'); navigate('/auth'); return }
    try { const res: any = await authApi.checkout(); if (res?.url) window.location.href = res.url; else message.error('Could not start subscription checkout.') }
    catch (e: any) { message.error(e?.response?.data?.detail || e?.message || 'Checkout failed') }
  }

  const buyCase = async (s: any) => {
    if (!user) { message.info('Please sign in to buy a case.'); navigate('/auth'); return }
    try {
      const res: any = await api.post(`/api/teaching/checkout/${s.id}`)
      if (res?.data?.url) window.location.href = res.data.url
      else if (res?.data?.already_owned) { message.success('You already own this case.'); loadList() }
    } catch (e: any) {
      if (e?.response?.status === 402) message.info('Single cases are for subscribers — set up a £25/year licence first.')
      else message.error(e?.response?.data?.detail || e?.message || 'Checkout failed')
    }
  }

  const startScenario = (s: any) => loadLesson(s.id, 0)

  const runAnalysis = async () => {
    if (!step?.endpoint) return
    setRunning(true)
    try { const res = await api.post(step.endpoint, step.payload || {}); setRunResult(res.data) }
    catch (e: any) { message.error(e?.response?.data?.detail || e?.message || 'Analysis failed') }
    finally { setRunning(false) }
  }

  const next = () => {
    if (isLast) {
      setTeachingActive(false); clearProgress()
      setSelected(null); setStepIdx(0); setChoice(null); setRevealed(false); setRunResult(null)
      message.success('Lesson complete — well done!'); navigate('/')
      return
    }
    const ni = stepIdx + 1; setStepIdx(ni); setChoice(null); setRevealed(false); setRunResult(null); persist(ni, null, false)
  }

  const onChoice = (val: number) => { setChoice(val); if (val !== step?.correct) setRevealed(true); persist(stepIdx, val, val !== step?.correct) }
  const onReveal = () => { setRevealed(true); persist(stepIdx, choice, true) }

  const renderStep = () => {
    if (!step) return null
    if (step.kind === 'info') {
      return (
        <Card>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Title level={4}>{step.emoji} {step.title}</Title>
            <Paragraph style={{ whiteSpace: 'pre-line', fontSize: 15 }}>{step.body}</Paragraph>
            <Button type="primary" onClick={next}>Continue</Button>
          </Space>
        </Card>
      )
    }
    if (step.kind === 'question') {
      return (
        <Card>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Title level={4}>{step.title}</Title>
            <Paragraph style={{ fontSize: 15 }}>{step.prompt}</Paragraph>
            <Radio.Group value={choice} onChange={(e) => onChoice(e.target.value)} style={{ width: '100%' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {step.options?.map((opt, i) => (
                  <Radio key={i} value={i} style={{ display: 'block', whiteSpace: 'normal', fontSize: 14 }}>{opt}</Radio>
                ))}
              </Space>
            </Radio.Group>
            {choice !== null && <Button type="primary" onClick={onReveal} disabled={revealed}>Check answer</Button>}
            {revealed && choice === step.correct && <Alert type="success" showIcon message="Correct!" description={step.why_correct} />}
            {revealed && choice !== null && choice !== step.correct && step.why_wrong?.[String(choice)] && (
              <Alert type="warning" showIcon message="Not quite — here's why" description={step.why_wrong[String(choice)]} />
            )}
            {step.hint && <Collapse ghost items={[{ key: 'h', label: '💡 Hint', children: <Text>{step.hint}</Text> }]} />}
            <Button onClick={next} disabled={!revealed}>Continue</Button>
          </Space>
        </Card>
      )
    }
    if (step.kind === 'run') {
      return (
        <Card>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Title level={4}>{step.title}</Title>
            <Paragraph style={{ fontSize: 15 }}>{step.prompt}</Paragraph>
            <Button type="primary" loading={running} onClick={runAnalysis}>Run the analysis</Button>
            {runResult && (<>
              <RenderResult data={runResult} />
              {step.explain && <Paragraph type="secondary">{step.explain}</Paragraph>}
              <Text strong style={{ color: '#005eb8' }}>This is a real result from the engine.</Text>
            </>)}
            <Divider style={{ margin: '8px 0' }} />
            <Button onClick={next} disabled={!runResult}>Continue — next step</Button>
          </Space>
        </Card>
      )
    }
    if (step.kind === 'summary') {
      return (
        <Card>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Title level={4}>{step.emoji} {step.title}</Title>
            <Paragraph style={{ whiteSpace: 'pre-line', fontSize: 15 }}>{step.body}</Paragraph>
            <Button type="primary" onClick={next}>Finish lesson</Button>
          </Space>
        </Card>
      )
    }
    return null
  }

  if (loadingData) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><Spin size="large" tip="Preparing your lesson..." /></div>
  }

  if (selected?.stepsLoaded) {
    return (
      <div style={{ maxWidth: 820, margin: '0 auto' }}>
        <Space size="small" style={{ marginBottom: 12 }}>
          <Tag color="blue">{selected.title}</Tag>
          <Text type="secondary">Step {stepIdx + 1} of {selected.steps.length}</Text>
        </Space>
        <div key={stepIdx}>{renderStep()}</div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 780, margin: '0 auto' }}>
      <Title level={3}>Teaching mode</Title>
      <Paragraph type="secondary">
        Learn medical statistics by doing — each case walks you from the hypothesis, through choosing the right test,
        to reading the results. The first case is free; extra cases are {teachPrice} each.
      </Paragraph>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {scenarios.map((s: any) => {
          const canBuy = !!user && !!user.licensed
          const owned = !!s.owned
          return (
            <Card key={s.id}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space>
                  <span style={{ fontSize: 30 }}>{s.emoji}</span>
                  <Title level={4} style={{ margin: 0 }}>{s.title}</Title>
                  {s.free ? <Tag color="green">Free</Tag> : <Tag color="gold">£1</Tag>}
                </Space>
                <Paragraph type="secondary" style={{ margin: 0 }}>{s.blurb}</Paragraph>
                <Space>
                  <Text type="secondary">{s.steps} steps</Text>
                  {s.free ? (<Button type="primary" onClick={() => startScenario(s)}>Start lesson</Button>)
                    : s.owned ? (<Button type="primary" onClick={() => startScenario(s)}>Start (your case)</Button>)
                    : canBuy ? (<Button type="primary" onClick={() => buyCase(s)}>Buy for £1</Button>)
                    : user ? (<Button onClick={() => subscribeFirst()}>Subscribe (£25/yr) to buy</Button>)
                    : (<Button onClick={() => { message.info('Please sign in to buy a case.'); navigate('/auth') }}>Sign in to unlock</Button>)}
                </Space>
              </Space>
            </Card>
          )
        })}
      </Space>
    </div>
  )
}

export default TeachingPage
