import React, { useEffect, useState } from 'react'
import { Card, Typography, Space, Button, Tag, message, Input } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../stores/authStore'
import { authApi } from '../api/authApi'
import { questionbankApi, datasetApi, pricingApi, gbp } from '../api/client'
import learnExercises from '../data/learnExercises.json'
import learnByDataset from '../data/learnByDataset.json'

const { Text } = Typography
const FREE_MAX = 10
const PRAC_KEY = 'devstat_practice_used'

interface Bank { id: string; title: string; blurb: string; emoji: string; price_cents: number; questions?: number; owned?: boolean; licensed?: boolean; free?: boolean }
interface Ex { number: string; topic: string; task: string; path: string; vars: string; answer: string; topic_num?: number }
interface Viewer { id: string; title: string; emoji: string; list: Ex[]; freeMax: number }

const practiceEx: Ex[] = (learnExercises as any).exercises || []
const byDataset = (learnByDataset as any) as { survival: Ex[]; qol: Ex[] }

const QuestionBanks: React.FC = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [banks, setBanks] = useState<Bank[]>([])
  const [viewer, setViewer] = useState<Viewer | null>(null)
  const [vIdx, setVIdx] = useState(0)
  const [vRevealed, setVRevealed] = useState<Record<string, boolean>>({})
  const [vUsed, setVUsed] = useState<number>(() => Number(localStorage.getItem(PRAC_KEY) || 0))
  const [loading, setLoading] = useState(false)
  const [qbPrice, setQbPrice] = useState('£5')
  const [subPrice, setSubPrice] = useState('£25')
  const [exId, setExId] = useState('')

  const unlimited = !!user && (user.licensed === true || user.plan === 'admin')
  const cur = viewer?.list?.[vIdx]

  const refresh = () => questionbankApi.list().then((r) => setBanks(r.data.banks || [])).catch(() => {})
  useEffect(() => {
    refresh()
    pricingApi.status().then((r) => {
      setQbPrice(gbp(r.data?.prices?.questionbank ?? 500))
      setSubPrice(gbp(r.data?.prices?.subscription ?? 2500))
    }).catch(() => {})
  }, [])

  const subscribe = async () => {
    if (!user) { message.info('Please sign in first.'); navigate('/auth'); return }
    try { const res: any = await authApi.checkout(); if (res?.url) window.location.href = res.url; else message.error('Could not start subscription checkout.') }
    catch (e: any) { message.error(e?.response?.data?.detail || e?.message || 'Checkout failed') }
  }

  const openPractice = async () => {
    if (!unlimited && vUsed >= FREE_MAX) { message.info(`You have finished your ${FREE_MAX} free practice questions — subscribe (£${subPrice}) to keep going.`); subscribe(); return }
    setLoading(true)
    try {
      await datasetApi.sample()
      window.dispatchEvent(new CustomEvent('devstat:data-changed'))
      setViewer({ id: 'practice', title: 'Practice (learn as you do)', emoji: '📘', list: practiceEx, freeMax: FREE_MAX })
      setExId('practice'); setVIdx(0); setVRevealed({})
    } catch { message.error('Could not load practice data.') }
    finally { setLoading(false) }
  }

  const openBank = async (b: Bank) => {
    if (!b.owned) return
    const list = byDataset[b.id] || []
    setLoading(true)
    try {
      await questionbankApi.load(b.id)
      window.dispatchEvent(new CustomEvent('devstat:data-changed'))
      setViewer({ id: b.id, title: b.title, emoji: b.emoji, list, freeMax: Infinity })
      setExId(b.id); setVIdx(0); setVRevealed({})
    } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || 'Could not open dataset') }
    finally { setLoading(false) }
  }

  const revealCur = () => {
    if (!cur) return
    if (vRevealed[cur.number]) return
    if (exId === 'practice' && !unlimited && vUsed >= FREE_MAX) { message.info(`That was your ${FREE_MAX} free practice questions — subscribe (£${subPrice}) to keep going.`); subscribe(); return }
    setVRevealed((p) => ({ ...p, [cur.number]: true }))
    if (exId === 'practice' && !unlimited) { const n = vUsed + 1; setVUsed(n); localStorage.setItem(PRAC_KEY, String(n)) }
  }

  const buy = async (b: Bank) => {
    if (!user) { message.info('Please sign in to buy.'); navigate('/auth'); return }
    try {
      const res: any = await questionbankApi.checkout(b.id)
      if (res?.data?.url) window.location.href = res.data.url
      else if (res?.data?.already_owned) { message.success('Already owned.'); refresh() }
    } catch (e: any) {
      if (e?.response?.status === 402) message.info('Question datasets are for subscribers — set up a £25/year licence first.')
      else message.error(e?.response?.data?.detail || e?.message || 'Checkout failed')
    }
  }

  if (viewer && cur) {
    const curDone = !!vRevealed[cur.number]
    const freeLeft = Math.max(0, FREE_MAX - vUsed)
    return (
      <div>
        <div style={{ background: '#eef7f6', border: '1px solid #ccfbf1', borderRadius: 10, padding: '8px 10px', marginBottom: 12, fontSize: 12, color: '#0f766e' }}>
          Load the dataset, do this task in the app yourself, then press <b>Check</b> to compare.
          The “You should see” line is the real result from DevStat.
        </div>
        <Space size="small" style={{ marginBottom: 8, width: '100%', justifyContent: 'space-between' }}>
          <Text strong style={{ fontSize: 14 }}>{viewer.emoji} {viewer.title}</Text>
          <Button size="small" type="text" onClick={() => setViewer(null)}>✕ back</Button>
        </Space>
        <Space size="small" style={{ marginBottom: 10 }}>
          <Text type="secondary">Question {vIdx + 1} of {viewer.list.length}</Text>
          <Tag color="teal">{cur.topic}</Tag>
        </Space>
        <Card size="small" style={{ borderColor: '#cdd7e0', background: '#fff' }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ background: '#0d9488', color: '#fff', borderRadius: 6, padding: '2px 8px', fontSize: 12, fontWeight: 700 }}>{cur.number}</span>
            </div>
            <Text style={{ fontWeight: 600, color: '#1f2937', fontSize: 14 }}>{cur.task}</Text>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <span style={{ background: '#f0fdfa', color: '#0f766e', border: '1px solid #ccfbf1', borderRadius: 6, padding: '2px 8px', fontSize: 12 }}>📍 {cur.path}</span>
              {cur.vars && <span style={{ background: '#f1f5f9', color: '#64748b', borderRadius: 6, padding: '2px 8px', fontSize: 12 }}>vars: {cur.vars}</span>}
            </div>
            <div style={{ borderTop: '1px dashed #e2e8f0', paddingTop: 10 }}>
              {curDone
                ? <div style={{ background: '#ecfdf5', borderLeft: '3px solid #10b981', borderRadius: 6, padding: '10px 12px', fontSize: 13, color: '#065f46' }}>{cur.answer}</div>
                : <Button size="small" type="primary" onClick={revealCur}>Check</Button>}
            </div>
          </Space>
        </Card>
        <Space style={{ marginTop: 10, width: '100%', justifyContent: 'space-between' }}>
          <Button size="small" disabled={vIdx === 0} onClick={() => setVIdx(vIdx - 1)}>‹ Prev</Button>
          <Input size="small" style={{ width: 80 }} type="number" min={1} max={viewer.list.length}
            defaultValue={vIdx + 1} onPressEnter={(e: any) => { const n = Number(e.target.value) - 1; if (n >= 0 && n < viewer.list.length) setVIdx(n) }} />
          <Button size="small" disabled={vIdx === viewer.list.length - 1} onClick={() => setVIdx(vIdx + 1)}>Next ›</Button>
        </Space>
        <div style={{ marginTop: 8, textAlign: 'center' }}>
          <Button size="small" type="link" onClick={() => setViewer(null)}>Back to datasets</Button>
        </div>
        {exId === 'practice' && (
          <Text type="secondary" style={{ display: 'block', marginTop: 10, fontSize: 12, textAlign: 'center' }}>
            {unlimited ? 'Unlimited.' : `First ${FREE_MAX} free. ${freeLeft} free attempt(s) left, then subscribe.`}
          </Text>
        )}
      </div>
    )
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Free practice module */}
      <div style={{ border: '1px solid #ccfbf1', borderRadius: 12, padding: 12, background: 'linear-gradient(180deg,#ffffff,#f0fdfa)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 18 }}>📘</span>
          <Text strong style={{ fontSize: 14 }}>Practice dataset</Text>
          <Tag color="teal" style={{ marginLeft: 'auto' }}>{practiceEx.length} exercises</Tag>
        </div>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          Synthetic practice data — run each test in the app, then check.
          {unlimited ? ' All unlocked.' : ` First ${FREE_MAX} questions free, then a ${subPrice}/yr licence unlocks everything.`}
        </Text>
        <Button size="small" block type="primary" onClick={openPractice} loading={loading}>
          {unlimited ? 'Start (all unlocked)' : `Start — first ${FREE_MAX} free`}
        </Button>
        {!unlimited && vUsed >= FREE_MAX && <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>You have used your {FREE_MAX} free questions — subscribe ({subPrice}/yr) to continue.</Text>}
      </div>

      {/* Paid dataset modules */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Text strong style={{ fontSize: 13, color: '#334155' }}>Question datasets</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>· {qbPrice} each, region-adjusted</Text>
      </div>
      {banks.filter((b) => !b.free).map((b) => (
        <div key={b.id} style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 12, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 18 }}>{b.emoji}</span>
            <Text strong style={{ fontSize: 14 }}>{b.title}</Text>
            {b.owned ? <Tag color="green" style={{ marginLeft: 'auto' }}>Owned</Tag> : <Tag color="gold" style={{ marginLeft: 'auto' }}>{qbPrice}</Tag>}
          </div>
          <div style={{ marginTop: 8 }}>
            {b.owned
              ? <Button size="small" type="primary" block onClick={() => openBank(b)} loading={loading}>Load dataset + answer exercises</Button>
              : <Button size="small" block onClick={() => { if (!b.licensed) { if (!user) { message.info('Please sign in to buy.'); navigate('/auth'); return } subscribe(); return } buy(b) }}>{b.licensed ? `Buy ${qbPrice}` : `Subscribe (${subPrice}/yr) to buy`}</Button>}
          </div>
        </div>
      ))}
    </Space>
  )
}

export default QuestionBanks
