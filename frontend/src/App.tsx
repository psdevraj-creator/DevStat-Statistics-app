import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography, Space, Dropdown, ConfigProvider, theme, Badge, Alert, Tag, Tooltip, message, Spin, Button, Modal, Segmented } from 'antd'
import {
  BarChartOutlined,
  TableOutlined,
  FundOutlined,
  ApartmentOutlined,
  RadarChartOutlined,
  ExperimentOutlined,
  NodeIndexOutlined,
  FileTextOutlined,
  MenuOutlined,
  GithubOutlined,
  QuestionCircleOutlined,
  UndoOutlined,
  RedoOutlined,
  SaveOutlined,
  FolderOpenOutlined,
  LoginOutlined,
  CrownOutlined,
  UserOutlined,
  DesktopOutlined,
} from '@ant-design/icons'
import HelpPanel from './components/HelpPanel'
import QuestionBanks from './components/QuestionBanks'
import DesktopEditionGate from './components/DesktopEditionGate'
import { useAuth } from './stores/authStore'
import { authApi } from './api/authApi'
import { getMode, setMode, pricingApi, gbp, datasetApi, setDesktopMode, desktopLicenceApi } from './api/client'

// ── Lazy-loaded pages ───────────────────────────────────────────────
const DataPage = React.lazy(() => import('./pages/DataPage'))
const TransformPage = React.lazy(() => import('./pages/TransformPage'))
const DescriptivePage = React.lazy(() => import('./pages/DescriptivePage'))
const ComparePage = React.lazy(() => import('./pages/ComparePage'))
const RegressionPage = React.lazy(() => import('./pages/RegressionPage'))
const SurvivalPage = React.lazy(() => import('./pages/SurvivalPage'))
const DiagnosticPage = React.lazy(() => import('./pages/DiagnosticPage'))
const GraphsPage = React.lazy(() => import('./pages/GraphsPage'))
const CorrelationPage = React.lazy(() => import('./pages/CorrelationPage'))
const OutputPage = React.lazy(() => import('./pages/OutputPage'))
const FactorPage = React.lazy(() => import('./pages/FactorPage'))
const FactorialAnovaPage = React.lazy(() => import('./pages/FactorialAnovaPage'))
const TestSuggestionPage = React.lazy(() => import('./pages/TestSuggestionPage'))
const WizardPage = React.lazy(() => import('./pages/WizardPage'))
const PowerPage = React.lazy(() => import('./pages/PowerPage'))
const ClusterPage = React.lazy(() => import('./pages/ClusterPage'))
const AuthPage = React.lazy(() => import('./pages/AuthPage'))
const TeachingPage = React.lazy(() => import('./pages/TeachingPage'))



const { Header, Content, Sider } = Layout
const { Text, Title } = Typography

// ── Global error logging ──────────────────────────────────────────────
import logStore from './stores/logStore'
import outputStore from './stores/outputStore'
if (typeof window !== 'undefined') {
  window.addEventListener('unhandledrejection', (event) => {
    const err = event.reason
    logStore.addEntry(
      'warning',
      'UnhandledPromise',
      err?.message || 'Unhandled promise rejection',
      err?.stack,
    )
  })
  window.addEventListener('error', (event) => {
    logStore.addEntry(
      'render',
      'WindowError',
      event.message || 'Unknown window error',
      event.error?.stack,
    )
  })
  // Expose log download so user can type window.__downloadLogs() in console
  ;(window as any).__downloadLogs = () => {
    const logs = logStore.getEntries()
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `devstat-logs-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
}

// Global flag so other components can check backend status without importing
export let isBackendOnline = false
export function setIsBackendOnline(v: boolean) { isBackendOnline = v }

const App: React.FC = () => {
  const { user, clearSession } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const prevPath = useRef(location.pathname)
  const [menuKey, setMenuKey] = useState('data')
  const [backendOnline, setBackendOnline] = useState(true)
  const [backendChecked, setBackendChecked] = useState(false)
  const backoffRef = useRef(1)
  const [showAuthPopup, setShowAuthPopup] = useState(false)
  const [showPaywall, setShowPaywall] = useState(false)
  const [usage, setUsage] = useState<{ licensed: boolean; analyses_left?: number; charts_left?: number } | null>(null)
  const [mode, setModeState] = useState<'exam' | 'live'>(() => (getMode() === 'live' ? 'live' : 'exam'))
  const [showLiveConsent, setShowLiveConsent] = useState(false)
  const [learnOpen, setLearnOpen] = useState(false)
  const [isDesktop, setIsDesktop] = useState(false)
  const [prices, setPrices] = useState<{ prices: { subscription: number; teaching: number; questionbank: number }; region_label: string } | null>(null)
  const subPrice = prices ? gbp(prices.prices.subscription) : '£25'
  const teachPrice = prices ? gbp(prices.prices.teaching) : '£1'
  const qbPrice = prices ? gbp(prices.prices.questionbank) : '£5'
  const regionLabel = prices?.region_label || 'your region'
  const isTeach = location.pathname.startsWith('/teaching')

  useEffect(() => { pricingApi.status().then((r) => setPrices(r.data)).catch(() => {}) }, [])
  // "?learn=1" opens the Learn-as-you-do pane on load (e.g. from the FRCR1 site)
  // and preloads the practice dataset so the user can start immediately.
  useEffect(() => {
    if (location.search.includes('learn=1')) {
      setLearnOpen(true)
      datasetApi.sample().then(() => { window.dispatchEvent(new CustomEvent('devstat:data-changed')) }).catch(() => {})
    }
  }, [location.search])

  const applyMode = (next: 'exam' | 'live') => { setMode(next); setModeState(next) }
  const changeMode = (next: 'exam' | 'live') => {
    if (next === 'live' && mode !== 'live') { setShowLiveConsent(true); return }
    applyMode(next)
  }
  const changeSegment = (v: any) => {
    if (v === 'teaching') { navigate('/teaching'); return }
    changeMode(v as 'exam' | 'live')
    if (isTeach) navigate(v === 'exam' ? '/' : '/')
  }

  // Unmissable "sign in" nudge for signed-out visitors (dismissable for
  // browsing; any compute attempt re-opens it — see the auth-required event).
  useEffect(() => {
    if (!user && !localStorage.getItem('devstat_dismiss_auth')) {
      const t = setTimeout(() => setShowAuthPopup(true), 600)
      return () => clearTimeout(t)
    }
  }, [user])

  // A signed-out use of an analysis/chart (blocked in the API client) re-opens
  // the sign-in prompt; a 402 (free tier used up) opens the paywall.
  useEffect(() => {
    const authRequired = () => {
      localStorage.removeItem('devstat_dismiss_auth')
      setShowAuthPopup(true)
    }
    const paywall = () => setShowPaywall(true)
    window.addEventListener('devstat:auth-required', authRequired)
    window.addEventListener('devstat:paywall', paywall)
    return () => {
      window.removeEventListener('devstat:auth-required', authRequired)
      window.removeEventListener('devstat:paywall', paywall)
    }
  }, [])

  // Refresh the free-tier usage badge whenever the user (or route) changes.
  useEffect(() => {
    if (!user) { setUsage(null); return }
    if (user.licensed) { setUsage({ licensed: true }); return }
    authApi.status().then((s: any) => setUsage({
      licensed: !!s.licensed,
      analyses_left: s.analyses_left,
      charts_left: s.charts_left,
    })).catch(() => { /* leave stale badge */ })
    if (isDesktop) {
      authApi.status().then((s: any) => {
        desktopLicenceApi.sync(!!s.licensed, s.licensed_until).catch(() => {})
      }).catch(() => {})
    }
  }, [user, location.pathname])

  const startCheckout = useCallback(async () => {
    if (!user) {
      message.info(`Please sign in to upgrade to a ${subPrice}/year DevStat licence.`)
      navigate('/auth')
      return
    }
    try {
      const res = await authApi.checkout()
      if (res?.url) {
        window.location.href = res.url
      } else {
        message.error('Could not start checkout. Try again.')
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || 'Checkout failed')
    }
  }, [user, navigate])

  // Clear frontend log on every app load
  useEffect(() => { logStore.clear() }, [])

  // Log every navigation
  useEffect(() => {
    if (prevPath.current !== location.pathname) {
      logStore.addEntry('info', 'navigation', `${prevPath.current} → ${location.pathname}`, '', {
        from: prevPath.current, to: location.pathname,
      })
      prevPath.current = location.pathname
    }
  }, [location.pathname])

  const [engineType, setEngineType] = useState<string>('')
  const [cloudRun, setCloudRun] = useState<boolean>(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [undoCount, setUndoCount] = useState(0)
  const [redoCount, setRedoCount] = useState(0)

  // ── Backend health check with exponential backoff ───────────────
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const check = async () => {
      try {
        const resp = await fetch('/api/health', { signal: AbortSignal.timeout(3000) })
        const online = resp.ok
        if (!cancelled) {
          setIsBackendOnline(online)
          setBackendOnline(online)
          setBackendChecked(true)
          backoffRef.current = 1
            if (online) {
            try { const data = await resp.json(); setEngineType(data.engine ?? ''); setCloudRun(!!data.cloud_run); const d = !!data.desktop; if (d) { setIsDesktop(true); setDesktopMode(true); setMode('live'); setModeState('live') } } catch {}
          }
          if (!online) schedule()
        }
      } catch {
        if (!cancelled) {
          setIsBackendOnline(false)
          setBackendOnline(false)
          setBackendChecked(true)
          schedule()
        }
      }
    }

    const schedule = () => {
      const delay = Math.min(backoffRef.current * 1000, 30000)
      backoffRef.current = Math.min(backoffRef.current * 2, 30)
      timer = setTimeout(check, delay)
    }

    check()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

  useEffect(() => {
    const path = location.pathname
    if (path === '/') setMenuKey('data')
    else if (path.startsWith('/analyze/descriptive')) setMenuKey('descriptive')
    else if (path.startsWith('/analyze/compare')) setMenuKey('compare')
    else if (path.startsWith('/analyze/regression')) setMenuKey('regression')
    else if (path.startsWith('/analyze/diagnostic')) setMenuKey('diagnostic')
    else if (path.startsWith('/analyze/correlation')) setMenuKey('correlation')
    else if (path.startsWith('/analyze/factor')) setMenuKey('factor')
    else if (path.startsWith('/analyze/factorial-anova')) setMenuKey('factorial-anova')
    else if (path.startsWith('/analyze/compare')) setMenuKey('compare')
    else if (path.startsWith('/survival')) setMenuKey('survival')
    else if (path.startsWith('/graphs')) setMenuKey('graphs')
    else if (path.startsWith('/wizard')) setMenuKey('wizard')
    else if (path.startsWith('/output')) setMenuKey('output')
    else if (path.startsWith('/transform')) setMenuKey('transform')
    else if (path.startsWith('/teaching')) setMenuKey('teaching')
    else if (path.startsWith('/syntax')) setMenuKey('syntax')
  }, [location])

  // ── Undo/Redo polling ──────────────────────────────────────────
  useEffect(() => {
    if (!backendOnline) return
    const t = setInterval(async () => {
      try {
        const r = await fetch('/api/data/undo-info', { signal: AbortSignal.timeout(3000) })
        if (r.ok) { const d = await r.json(); setUndoCount(d.undo_count ?? 0); setRedoCount(d.redo_count ?? 0) }
      } catch { /* silent poll failure */ }
    }, 5000)
    return () => clearInterval(t)
  }, [backendOnline])

  const handleUndo = async () => {
    try {
      const r = await fetch('/api/data/undo', { method: 'POST', signal: AbortSignal.timeout(5000) })
      if (r.ok) { const d = await r.json(); setUndoCount(d.undo_count ?? 0); setRedoCount(d.redo_count ?? 0); window.dispatchEvent(new CustomEvent('devstat:data-changed')) }
    } catch { message.warning('Undo failed') }
  }

  const handleRedo = async () => {
    try {
      const r = await fetch('/api/data/redo', { method: 'POST', signal: AbortSignal.timeout(5000) })
      if (r.ok) { const d = await r.json(); setUndoCount(d.undo_count ?? 0); setRedoCount(d.redo_count ?? 0); window.dispatchEvent(new CustomEvent('devstat:data-changed')) }
    } catch { message.warning('Redo failed') }
  }

  // ── Download frontend logs ──────────────────────────────────────
  const downloadLogs = () => {
    const frontendLogs = logStore.getEntries()

    const payload = JSON.stringify({
      downloadedAt: new Date().toISOString(),
      frontendLogCount: frontendLogs.length,
      frontendLogs,
      backendLogs: '(captured in Cloud Logging)',
    }, null, 2)

    const blob = new Blob([payload], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `devstat-logs-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Save / Load project ────────────────────────────────────────────
  const loadInputRef = useRef<HTMLInputElement>(null)

  const saveProject = async () => {
    try {
      const outputs = outputStore.getEntries()
      const resp = await fetch('/api/project/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outputs }),
      })
      if (!resp.ok) throw new Error(`Save failed: ${resp.status}`)
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `devstat-project-${new Date().toISOString().slice(0, 10)}.devstat`
      a.click()
      URL.revokeObjectURL(url)
      message.success('Project saved')
    } catch (e: any) {
      message.error(`Save failed: ${e.message}`)
    }
  }

  const loadProject = async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    try {
      const resp = await fetch('/api/project/load', { method: 'POST', body: form })
      if (!resp.ok) throw new Error(`Load failed: ${resp.status}`)
      const data = await resp.json()
      if (data.outputs) {
        outputStore.clearAll()
        data.outputs.forEach((o: any) => outputStore.addEntry(o.type, o.title, o.result))
      }
      window.dispatchEvent(new CustomEvent('devstat:data-changed'))
      message.success(`Project loaded: ${data.filename || 'untitled'} (${data.rows} rows)`)
    } catch (e: any) {
      message.error(`Load failed: ${e.message}`)
    }
  }

  const handleLoadClick = () => { loadInputRef.current?.click() }

  const handleLoadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { loadProject(f); e.target.value = '' }
  }

  // ── Keyboard shortcut: Ctrl+Shift+D → download logs ──────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault()
        downloadLogs()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleMenuClick = (key: string) => {
    setMenuKey(key)
    switch (key) {
      case 'data': case 'data-view': case 'data-compute': case 'data-recode': navigate('/'); break
      case 'descriptive': case 'frequencies': case 'crosstab': case 'explore':
        navigate('/analyze/descriptive'); break
      case 'compare': case 'anova': case 'means':
      case 'np-mannwhitney': case 'np-wilcoxon': case 'np-kruskalwallis':
      case 'np-friedman': case 'np-mcnemar': case 'np-sign': case 'np-binomial':
      case 'np-runs': case 'np-ks': case 'chisquare':
        navigate('/analyze/compare'); break
      case 'factorial-anova': navigate('/analyze/factorial-anova'); break
      case 'regression': case 'logistic': case 'mixed-model':
        navigate('/analyze/regression'); break
      case 'correlation': case 'partial-correlation':
        navigate('/analyze/correlation'); break
      case 'factor': case 'reliability': navigate('/analyze/factor'); break
      case 'cluster': navigate('/analyze/cluster'); break
      case 'power': navigate('/analyze/power'); break
      case 'diagnostic': case 'roc': navigate('/analyze/diagnostic'); break
      case 'survival': case 'kaplan-meier': case 'cox': navigate('/survival'); break
      case 'graphs': navigate('/graphs'); break
      case 'wizard': navigate('/wizard'); break
      case 'transform': navigate('/transform'); break
      case 'output': navigate('/output'); break
      case 'suggest': navigate('/suggest'); break
      case 'teaching': navigate('/teaching'); break
    }
  }

  const menuItems = [
    { key: 'data', label: 'Data', icon: <TableOutlined />,
      children: [
        { key: 'data-view', label: 'Data View' },
        { key: 'transform', label: 'Transform' },
      ] 
    },
    {
      key: 'analyze',
      label: 'Analyze',
      icon: <FundOutlined />,
      children: [
        { key: 'descriptive', label: 'Descriptive' },
        { key: 'frequencies', label: 'Frequencies' },
        { key: 'crosstab', label: 'Crosstabs' },
        { key: 'explore', label: 'Explore' },
        { key: 'div1', type: 'divider' as const },
        { key: 'compare', label: 'Compare Means' },
        { key: 'anova', label: 'One-way ANOVA' },
        { key: 'means', label: 'Means' },
        { key: 'factorial-anova', label: 'Factorial ANOVA' },
        { key: 'div2', type: 'divider' as const },
        { key: 'nonparametric', label: 'Non-parametric Tests',
          children: [
            { key: 'np-mannwhitney', label: 'Mann-Whitney U' },
            { key: 'np-wilcoxon', label: 'Wilcoxon Signed-Rank' },
            { key: 'np-kruskalwallis', label: 'Kruskal-Wallis' },
            { key: 'np-friedman', label: 'Friedman' },
            { key: 'np-mcnemar', label: "McNemar's" },
            { key: 'np-sign', label: 'Sign Test' },
            { key: 'np-binomial', label: 'Binomial Test' },
            { key: 'np-runs', label: 'Runs Test' },
            { key: 'np-ks', label: 'Kolmogorov-Smirnov' },
          ],
        },
        { key: 'chisquare', label: 'Chi-square Test' },
        { key: 'div3', type: 'divider' as const },
        { key: 'correlation', label: 'Correlation' },
        { key: 'partial-correlation', label: 'Partial Correlation' },
        { key: 'div4', type: 'divider' as const },
        { key: 'regression', label: 'Linear Regression' },
        { key: 'logistic', label: 'Logistic Regression' },
        { key: 'mixed-model', label: 'Mixed Model' },
        { key: 'div5', type: 'divider' as const },
        { key: 'factor', label: 'Factor Analysis' },
        { key: 'reliability', label: 'Reliability' },
        { key: 'cluster', label: 'Cluster Analysis' },
        { key: 'power', label: 'Power Analysis' },
        { key: 'div6', type: 'divider' as const },
        { key: 'diagnostic', label: 'Diagnostic Test' },
        { key: 'roc', label: 'ROC Curve' },
        { key: 'div7', type: 'divider' as const },
        { key: 'suggest', label: 'Suggest Test' },
      ],
    },
    { key: 'survival', label: 'Survival', icon: <ApartmentOutlined />,
      children: [
        { key: 'kaplan-meier', label: 'Kaplan-Meier' },
        { key: 'cox', label: 'Cox Regression' },
      ],
    },
    { key: 'graphs', label: 'Graphs', icon: <BarChartOutlined /> },
    { key: 'wizard', label: 'Wizard', icon: <QuestionCircleOutlined /> },
    ...(isDesktop ? [] : [{ key: 'teaching', label: 'Teaching', icon: <CrownOutlined /> }]),

    { key: 'output', label: 'Output', icon: <FileTextOutlined /> },
  ]

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#005eb8',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          borderRadius: 6,
        },
      }}
    >
      <DesktopEditionGate enabled={isDesktop}>
      <Layout style={{ height: '100vh', overflow: 'hidden' }}>
        {/* Gradient Header */}
        <Header
          style={{
            background: 'linear-gradient(135deg, #003d8b 0%, #005eb8 50%, #1a7fd4 100%)',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 56,
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
          }}
        >
          <Space size={12} style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
            <RadarChartOutlined style={{ fontSize: 28, color: '#fff' }} />
            <div>
              <Text style={{ color: '#fff', fontSize: 20, fontWeight: 700, letterSpacing: 1, lineHeight: 1.2, display: 'block' }}>
                DevStat
              </Text>
              <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 11, fontWeight: 400, letterSpacing: 0.5, display: 'block' }}>
                Medical Statistics
              </Text>
            </div>
          </Space>

          <Space size={4} style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: 16 }}>
            <Tooltip title="Save project (.devstat)">
              <SaveOutlined style={{ color: 'rgba(255,255,255,0.8)', fontSize: 16, cursor: 'pointer' }}
                onClick={saveProject} />
            </Tooltip>
            <Tooltip title="Load project (.devstat)">
              <FolderOpenOutlined style={{ color: 'rgba(255,255,255,0.8)', fontSize: 16, cursor: 'pointer' }}
                onClick={handleLoadClick} />
            </Tooltip>
            <input ref={loadInputRef} type="file" accept=".devstat" style={{ display: 'none' }} onChange={handleLoadFile} />
          </Space>

          <Space size={4} style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: 16 }}>
            <Tooltip title={`Undo${undoCount > 0 ? ` (${undoCount} available)` : ''}`}>
              <UndoOutlined style={{ color: undoCount > 0 ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.3)', fontSize: 16, cursor: undoCount > 0 ? 'pointer' : 'default' }}
                onClick={() => { if (undoCount > 0) handleUndo() }} />
            </Tooltip>
            <Tooltip title={`Redo${redoCount > 0 ? ` (${redoCount} available)` : ''}`}>
              <RedoOutlined style={{ color: redoCount > 0 ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.3)', fontSize: 16, cursor: redoCount > 0 ? 'pointer' : 'default' }}
                onClick={() => { if (redoCount > 0) handleRedo() }} />
            </Tooltip>
          </Space>

          <Space size={16}>
            {!isDesktop && (
              <>
              <Tooltip title="Exam = synthetic data only · Live = data kept only in memory (never stored) · Teaching = guided lessons. Switching to Live asks you to confirm.">
              <Segmented
                size="small"
                value={isTeach ? 'teaching' : mode}
                onChange={(v) => changeSegment(v)}
                options={[{ label: 'Exam', value: 'exam' }, { label: 'Live', value: 'live' }, { label: 'Teaching', value: 'teaching' }]}
                style={{ background: 'rgba(255,255,255,0.18)' }}
              />
              </Tooltip>
              <Tooltip title="Learn as you do — practice datasets with 100 questions each (different from Teaching mode's guided scenarios). Prices adjusted to your region ({regionLabel}).">
              <Button size="small" icon={<QuestionCircleOutlined />} onClick={() => setLearnOpen(!learnOpen)}>Learn as you do</Button>
              </Tooltip>
              </>
            )}
            {isDesktop && (
              <Tooltip title="Desktop Edition — runs fully offline on this machine. Your data never leaves it.">
                <Tag style={{ color: '#fff', background: 'rgba(255,255,255,0.18)', borderColor: 'rgba(255,255,255,0.35)', margin: 0 }}>
                  <DesktopOutlined /> Desktop Edition
                </Tag>
              </Tooltip>
            )}
            {user ? (
              <Dropdown
                menu={{ items: [
                  { key: 'acct', label: user.name || user.email || 'Account', disabled: true },
                  { type: 'divider' },
                  ...(user.licensed ? [] : [{ key: 'upgrade', label: `Upgrade — ${subPrice}/year licence` }]),
                  { key: 'logout', label: 'Sign out', danger: true },
                ], onClick: ({ key }) => { if (key === 'logout') { clearSession(); message.success('Signed out') } else if (key === 'upgrade') { startCheckout() } } }}
                placement="bottomRight"
              >
                <Button size="small" style={{ background: 'transparent', borderColor: 'rgba(255,255,255,0.4)', color: '#fff' }} icon={<UserOutlined />}>
                  {user.name || user.email || 'Account'}
                </Button>
              </Dropdown>
            ) : (
              <Button size="small" type="primary" icon={<LoginOutlined />} onClick={() => navigate('/auth')}>
                Sign in
              </Button>
            )}
            {user && !user.licensed && (
              <Tooltip title="Free tier — 5 analyses and 5 charts per machine/address. Upgrade for unlimited.">
                <Tag style={{ color: '#fff', background: 'rgba(255,255,255,0.15)', borderColor: 'rgba(255,255,255,0.3)' }}>
                  {usage && usage.licensed ? 'Licensed' : usage && typeof usage.analyses_left === 'number'
                    ? `${usage.analyses_left} analyses · ${usage.charts_left} charts left`
                    : 'Free'}
                </Tag>
              </Tooltip>
            )}
            {user && !user.licensed && (
              <Button size="small" type="primary" icon={<CrownOutlined />} onClick={startCheckout}>
                Upgrade
              </Button>
            )}
            <Tooltip title="Help">
              <QuestionCircleOutlined
                style={{ color: 'rgba(255,255,255,0.8)', fontSize: 18, cursor: 'pointer' }}
                onClick={() => setHelpOpen(true)}
              />
            </Tooltip>

            <Dropdown
              menu={{
                items: [
                  { key: 'help', label: 'Open Help', icon: <QuestionCircleOutlined /> },
                  { key: 'about', label: 'About DevStat', icon: <FileTextOutlined /> },
                  { type: 'divider' },
                  { key: 'github', label: 'GitHub', icon: <GithubOutlined /> },
                ],
                onClick: ({ key }) => {
                  if (key === 'help') setHelpOpen(true)
                  else if (key === 'github') window.open('https://github.com/anomalyco/devstat', '_blank')
                },
              }}
              placement="bottomRight"
            >
              <QuestionCircleOutlined style={{ color: 'rgba(255,255,255,0.8)', fontSize: 18, cursor: 'pointer' }} />
            </Dropdown>
          </Space>
        </Header>

        {/* SPSS-style Menu Bar */}
        <div style={{ background: '#fff', borderBottom: '1px solid #e2e8f0', padding: '0 16px' }}>
          <Menu
            mode="horizontal"
            selectedKeys={[menuKey]}
            items={menuItems}
            onClick={({ key }) => handleMenuClick(key)}
            style={{ borderBottom: 'none', background: 'transparent', fontSize: 13 }}
          />
        </div>

        {/* Backend Offline Banner */}
        {backendChecked && !backendOnline && (
          <Alert
            message="Backend is not running"
            description="The DevStat backend server is unreachable. Start it via launch_gui.bat or run: py -3.14 -m uvicorn app.main:create_app --factory in the backend/ directory."
            type="error"
            showIcon
            closable={false}
            style={{ borderRadius: 0, border: 'none' }}
          />
        )}

        {/* Online (Cloud Run) mode banner */}
        {cloudRun && mode === 'live' && (
          <Alert
            message="Live / confidential mode — temporary, never stored"
            description="Your data goes to Google's servers only to run the calculation you asked for. It is held briefly in memory and then deleted — it is not stored, saved, or kept anywhere. If you'd rather your data never leave your machine, use the offline desktop version."
            type="info"
            showIcon
            closable={false}
            style={{ borderRadius: 0, border: 'none', background: '#e6f4ff', borderBottom: '1px solid #bae0ff' }}
          />
        )}

        {/* Main Content + inline "Learn as you do" pane (scrollable, not overlay) */}
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          <Content style={{ padding: 16, background: '#f1f5f9', flex: 1, overflow: 'auto' }}>
            <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" tip="Loading..." /></div>}>
            <Routes>
              <Route path=
                "/" element={<DataPage />} />
            <Route path=
                "/analyze/descriptive" element={<DescriptivePage />} />
            <Route path=
                "/analyze/compare" element={<ComparePage />} />
            <Route path=
                "/analyze/regression" element={<RegressionPage />} />
            <Route path=
                "/analyze/diagnostic" element={<DiagnosticPage />} />
            <Route path=
                "/analyze/correlation" element={<CorrelationPage />} />
            <Route path=
                "/analyze/factor" element={<FactorPage />} />
            <Route path=
                "/analyze/factorial-anova" element={<FactorialAnovaPage />} />
            <Route path=
                "/survival" element={<SurvivalPage />} />
            <Route path="/graphs" element={<GraphsPage />} />
            <Route path="/suggest" element={<TestSuggestionPage />} />
            <Route path="/wizard" element={<WizardPage />} />
            <Route path="/transform" element={<TransformPage />} />
            <Route path=
                "/output" element={<OutputPage />} />
            <Route path="/analyze/power" element={<PowerPage />} />
            <Route path="/analyze/cluster" element={<ClusterPage />} />
            <Route path="/teaching" element={<TeachingPage />} />
            <Route path="/auth" element={<AuthPage />} />

            </Routes>
            </Suspense>
          </Content>
          {learnOpen && (
            <aside style={{ width: 400, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0, background: '#f8fafc', borderLeft: '1px solid #e2e8f0' }}>
              <div style={{ padding: '12px 14px', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <Text strong style={{ fontSize: 14 }}>Learn as you do</Text>
                    <div style={{ fontSize: 12, color: '#64748b' }}>Do the task in the app, then check.</div>
                  </div>
                  <Button size="small" type="text" onClick={() => setLearnOpen(false)} aria-label="Close">✕</Button>
                </div>
              </div>
              <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 12 }}>
                <QuestionBanks />
              </div>
            </aside>
          )}
        </div>
      </Layout>
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />
      <Modal
        open={showAuthPopup}
        onCancel={() => { setShowAuthPopup(false); localStorage.setItem('devstat_dismiss_auth', '1') }}
        footer={null}
        centered
        width={460}
      >
        <div style={{ textAlign: 'center', padding: '8px 4px' }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>👋</div>
          <Typography.Title level={4} style={{ marginBottom: 8 }}>A warm hello!</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
            Pop in with a quick free account and we'll save your work and keep it safe for you.
            Your first <b>5 analyses and 5 charts</b> are free, no card needed.
            <br /><br />
            And if you ever want more? It's just <b>{subPrice} a year</b> — that's less than a barista
            coffee each week. Less than two takeaway lunches a month. Pocket change, honestly,
            and you can use it all you like. <Text type="secondary">(Adjusted for {regionLabel}.)</Text>
          </Typography.Paragraph>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button type="primary" block size="large" onClick={() => { setShowAuthPopup(false); navigate('/auth') }}>
              Create your free account
            </Button>
            <Button block onClick={() => { setShowAuthPopup(false); localStorage.setItem('devstat_dismiss_auth', '1') }}>
              Maybe later
            </Button>
          </Space>
        </div>
      </Modal>

      {/* Paywall — a guest (or free user) has used up the free 5 analyses + 5 charts */}
      <Modal
        open={showPaywall}
        onCancel={() => setShowPaywall(false)}
        footer={null}
        centered
        width={460}
      >
        <div style={{ textAlign: 'center', padding: '8px 4px' }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>✨</div>
          <Typography.Title level={4} style={{ marginBottom: 8 }}>You've had a lovely free run of it!</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
            That's your 5 analyses and 5 charts — well done, you really know your way around this.
            If you'd like to keep going, it's just <b>{subPrice} a year</b> — like one pub lunch, or a
            coffee a week, for the whole year of unlimited number-crunching. <Text type="secondary">(Adjusted for {regionLabel}.)</Text>
          </Typography.Paragraph>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button type="primary" block size="large" icon={<CrownOutlined />} onClick={() => { setShowPaywall(false); startCheckout() }}>
              Upgrade — {subPrice}/year
            </Button>
            <Button block onClick={() => setShowPaywall(false)}>
              Maybe later
            </Button>
          </Space>
        </div>
      </Modal>

      {/* Live / confidential mode consent */}
      <Modal
        open={showLiveConsent}
        onCancel={() => setShowLiveConsent(false)}
        footer={null}
        centered
        width={470}
      >
        <div style={{ textAlign: 'center', padding: '8px 4px' }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>💛</div>
          <Typography.Title level={4} style={{ marginBottom: 8 }}>A gentle note about your data</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
            Okay, lovely — just so you know exactly what happens when you use <b>Live mode</b>.
            Your data only travels to Google's servers to run the calculation you've asked for,
            and that's all. It's held very briefly in memory while we work, then it's gone — we
            don't save it, we don't store it, and we don't keep a copy of it anywhere.
            <br /><br />
            And if even that little trip isn't for you — no worries, truly. The offline version
            on your own machine keeps everything safely at home. Whatever you choose, we're just
            glad you're here.
          </Typography.Paragraph>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button type="primary" block size="large" onClick={() => { applyMode('live'); setShowLiveConsent(false) }}>
              Enable Live mode
            </Button>
            <Button block onClick={() => setShowLiveConsent(false)}>
              No thanks, I'll use offline
            </Button>
          </Space>
        </div>
      </Modal>
      </DesktopEditionGate>
    </ConfigProvider>
  )
}

export default App
