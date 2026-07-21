import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography, Space, Dropdown, ConfigProvider, theme, Badge, Alert, Tag, Tooltip, message, Spin } from 'antd'
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
} from '@ant-design/icons'
import HelpPanel from './components/HelpPanel'

// ── Lazy-loaded pages ───────────────────────────────────────────────
const DataPage = React.lazy(() => import('./pages/DataPage'))
const TransformPage = React.lazy(() => import('./pages/TransformPage'))
const DescriptivePage = React.lazy(() => import('./pages/DescriptivePage'))
const ComparePage = React.lazy(() => import('./pages/ComparePage'))
const RegressionPage = React.lazy(() => import('./pages/RegressionPage'))
const SurvivalPage = React.lazy(() => import('./pages/SurvivalPage'))
const DiagnosticPage = React.lazy(() => import('./pages/DiagnosticPage'))
const GraphsPage = React.lazy(() => import('./pages/GraphsPage'))
const SyntaxPage = React.lazy(() => import('./pages/SyntaxPage'))
const CorrelationPage = React.lazy(() => import('./pages/CorrelationPage'))
const OutputPage = React.lazy(() => import('./pages/OutputPage'))
const FactorPage = React.lazy(() => import('./pages/FactorPage'))
const FactorialAnovaPage = React.lazy(() => import('./pages/FactorialAnovaPage'))
const TestSuggestionPage = React.lazy(() => import('./pages/TestSuggestionPage'))
const WizardPage = React.lazy(() => import('./pages/WizardPage'))
const PowerPage = React.lazy(() => import('./pages/PowerPage'))
const ClusterPage = React.lazy(() => import('./pages/ClusterPage'))



const { Header, Content, Sider } = Layout
const { Text, Title } = Typography

// ── Global error logging ──────────────────────────────────────────────
import logStore from './stores/logStore'
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
  const navigate = useNavigate()
  const location = useLocation()
  const prevPath = useRef(location.pathname)
  const [menuKey, setMenuKey] = useState('data')
  const [backendOnline, setBackendOnline] = useState(true)
  const [backendChecked, setBackendChecked] = useState(false)
  const backoffRef = useRef(1)

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
            try { const data = await resp.json(); setEngineType(data.engine ?? ''); setCloudRun(!!data.cloud_run) } catch {}
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
    else if (path.startsWith('/syntax')) setMenuKey('syntax')
    else if (path.startsWith('/ai')) setMenuKey('ai')
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

  // ── Download ALL logs (frontend + backend) ──────────────────────
  const downloadLogs = async () => {
    const frontendLogs = logStore.getEntries()

    let backendLogs = ''
    try {
      const resp = await fetch('/api/logs')
      if (resp.ok) backendLogs = await resp.text()
    } catch {}

    const payload = JSON.stringify({
      downloadedAt: new Date().toISOString(),
      frontendLogCount: frontendLogs.length,
      frontendLogs,
      backendLogs: backendLogs ? backendLogs.slice(0, 50000) : '(unavailable)',
    }, null, 2)

    const blob = new Blob([payload], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `devstat-logs-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
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
      case 'syntax': navigate('/syntax'); break
      case 'wizard': navigate('/wizard'); break
      case 'transform': navigate('/transform'); break
      case 'output': navigate('/output'); break
      case 'suggest': navigate('/suggest'); break
      case 'ai': navigate('/ai'); break
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
    { key: 'syntax', label: 'Syntax', icon: <FileTextOutlined /> },
    { key: 'wizard', label: 'Wizard', icon: <QuestionCircleOutlined /> },

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
      <Layout style={{ minHeight: '100vh' }}>
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
                  { key: 'download-logs', label: `Download Logs (${logStore.getEntries().length})`, icon: <FileTextOutlined /> },
                  { key: 'download-logs-verbose', label: 'Download Logs + Backend (full debug)', icon: <FileTextOutlined />, danger: true },
                  { type: 'divider' },
                  { key: 'github', label: 'GitHub', icon: <GithubOutlined /> },
                ],
                onClick: ({ key }) => {
                  if (key === 'help') setHelpOpen(true)
                  else if (key === 'download-logs' || key === 'download-logs-verbose') downloadLogs()
                  else if (key === 'github') window.open('https://github.com/anomalyco/devstat', '_blank')
                },
              }}
              placement="bottomRight"
            >
              <Badge count={logStore.getEntries().length} size="small" offset={[2, -2]}>
                <QuestionCircleOutlined style={{ color: 'rgba(255,255,255,0.8)', fontSize: 18, cursor: 'pointer' }} />
              </Badge>
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

        {backendOnline && cloudRun && (
          <Alert
            message="🔒 Zero Data Retention"
            description="All data is processed in memory only and never stored, logged, or written to disk. Your privacy is protected."
            type="info"
            showIcon
            closable={false}
            style={{ borderRadius: 0, border: 'none', background: '#e8f4fd', textAlign: 'center' }}
          />
        )}

        {/* Main Content */}
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
            <Route path="/syntax" element={<SyntaxPage />} />
            <Route path=
                "/output" element={<OutputPage />} />
            <Route path="/analyze/power" element={<PowerPage />} />
            <Route path="/analyze/cluster" element={<ClusterPage />} />

          </Routes>
          </Suspense>
        </Content>
      </Layout>
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />
    </ConfigProvider>
  )
}

export default App
