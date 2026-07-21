import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Card, Button, Input, Space, Typography, Spin, Alert, Tag, Modal,
  Select, Row, Col, Upload, Divider, Empty, Tooltip, Skeleton,
  message as antMessage, ConfigProvider, theme,
} from 'antd'
import {
  SendOutlined, RobotOutlined, UserOutlined,
  CheckCircleOutlined, CloseCircleOutlined, EditOutlined,
  DeleteOutlined, ReloadOutlined, HistoryOutlined,
  ThunderboltOutlined, InboxOutlined, BulbOutlined,
  SoundOutlined, FieldNumberOutlined,
} from '@ant-design/icons'
import { api, datasetApi } from '../api/client'
import ChartRenderer from '../components/ChartRenderer'
import outputStore from '../stores/outputStore'

const { Text, Title, Paragraph } = Typography
const { TextArea } = Input
const { Dragger } = Upload

// ── Types ─────────────────────────────────────────────────────────────

interface ChartProposal {
  type: string
  title: string
  endpoint: string
  payload: Record<string, any>
}

interface TestProposal {
  id: string
  test: string
  test_name: string
  rationale: string
  endpoint: string
  payload: Record<string, any>
  charts: ChartProposal[]
  assumptions: string[]
  fallback_test: string | null
  user_confirmed: boolean
  user_removed: boolean
}

interface AnalysisPlan {
  plan_name: string
  tests: TestProposal[]
  notes: string
}

interface TestResult {
  test_id: string
  test_name: string
  status: string
  endpoint: string
  response: Record<string, any>
  charts: { type: string; title: string; data: Record<string, any> }[]
  error: string | null
  used_fallback: boolean
  fallback_reason: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  plan?: AnalysisPlan
  results?: TestResult[]
  answer?: { summary: string; detailed_results: any[]; limitations: string; conclusion: string }
  loading?: boolean
  progressLabel?: string
}

// ── Icons per test type ──────────────────────────────────────────────

const TEST_ICONS: Record<string, string> = {
  independent_ttest: '🔬', paired_ttest: '🔬', mannwhitney: '📊',
  wilcoxon: '📊', oneway_anova: '📈', chisquare: '📋', fisher_exact: '📋',
  pearson: '📉', spearman: '📉', linear_regression: '📐',
  logistic_regression: '📐', kaplan_meier: '📅', cox_regression: '📅',
  diagnostic_test: '🩺', descriptive: '📊', frequencies: '📊',
}

// ── Animated loading dots ────────────────────────────────────────────

const LoadingDots: React.FC<{ label?: string }> = ({ label }) => (
  <Space>
    <Spin size="small" />
    <Text type="secondary" style={{ animation: 'pulse 1.5s ease-in-out infinite' }}>
      {label || 'Thinking...'}
    </Text>
  </Space>
)

// ── AiPage Component ──────────────────────────────────────────────────

const AiPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [datasetInfo, setDatasetInfo] = useState<any>(null)
  const [datasetLoading, setDatasetLoading] = useState(true)
  const [currentPlan, setCurrentPlan] = useState<AnalysisPlan | null>(null)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingTest, setEditingTest] = useState<TestProposal | null>(null)
  const [executing, setExecuting] = useState(false)
  const [history, setHistory] = useState<any[]>([])
  const [apiKeyMissing, setApiKeyMissing] = useState(false)
  const lastQuestionRef = useRef<string>('')

  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<any>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    loadDatasetInfo()
    loadHistory()
  }, [])

  const loadDatasetInfo = async () => {
    setDatasetLoading(true)
    try {
      const res = await api.get('/api/data/info')
      setDatasetInfo(res.data)
    } catch { setDatasetInfo(null) }
    finally { setDatasetLoading(false) }
  }

  const loadHistory = async () => {
    try {
      const res = await api.get('/api/ai/history?limit=8')
      setHistory(res.data || [])
    } catch { /* ok */ }
  }

  // ── Upload ───────────────────────────────────────────────────────
  const handleUpload = async (file: File) => {
    try {
      const res = await datasetApi.upload(file)
      setDatasetInfo(res.data)
      antMessage.success(`Dataset "${file.name}" loaded (${res.data.rows} rows × ${res.data.cols} cols)`)
      addMessage('assistant', `✅ Dataset **${file.name}** loaded (${res.data.rows} rows, ${res.data.cols} columns). What would you like to analyze?`)
    } catch (err: any) {
      antMessage.error(err?.response?.data?.detail || 'Upload failed')
    }
    return false
  }

  // ── Chat message helpers ────────────────────────────────────────
  const addMessage = (role: 'user' | 'assistant', content: string, extras?: Partial<ChatMessage>) => {
    setMessages(prev => [...prev, { role, content, ...extras } as ChatMessage])
  }

  const updateLastMessage = (updates: Partial<ChatMessage>) => {
    setMessages(prev => {
      const copy = [...prev]
      if (copy.length > 0) copy[copy.length - 1] = { ...copy[copy.length - 1], ...updates }
      return copy
    })
  }

  // ── Send message ────────────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setSending(true)
    lastQuestionRef.current = text

    addMessage('user', text)
    addMessage('assistant', '', { loading: true, progressLabel: '🤖 Analysing your question...' })

    try {
      updateLastMessage({ progressLabel: '📡 Consulting biostatistician AI...' })
      const res = await api.post('/api/ai/parse', { question: text })

      if (res.status === 200 && res.data?.plan?.tests?.length > 0) {
        const plan: AnalysisPlan = res.data.plan
        setCurrentPlan(plan)
        updateLastMessage({
          loading: false,
          content: `I've prepared an analysis plan. **${plan.tests.length} test(s)** proposed — please review below:`,
          plan,
        })
      } else {
        updateLastMessage({
          loading: false,
          content: `⚠️ I couldn't determine appropriate tests. ${res.data?.plan?.notes || 'Please provide more detail or check your data.'}`,
        })
      }
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 500 && err?.response?.data?.detail?.includes('API key')) {
        setApiKeyMissing(true)
        updateLastMessage({ loading: false, content: '❌ **LLM API key not configured.** Set `DEEPSEEK_API_KEY` in the backend `.env` file and restart the server.' })
      } else {
        const detail = err?.response?.data?.detail || 'Failed to analyse question. Please try rephrasing.'
        updateLastMessage({ loading: false, content: `❌ **Error:** ${detail}` })
      }
    } finally { setSending(false) }
  }, [input, sending, messages])

  // ── Confirm & Execute ───────────────────────────────────────────
  const handleConfirmRun = async () => {
    if (!currentPlan) return
    setExecuting(true)

    const confirmedPlan = {
      ...currentPlan,
      tests: currentPlan.tests.map(t => ({ ...t, user_confirmed: true, user_removed: false })),
    }

    addMessage('assistant', '', { loading: true, progressLabel: '⏳ Starting execution...' })

    try {
      const total = confirmedPlan.tests.length

      // Execute each test once, collecting results incrementally
      const allResults: TestResult[] = []
      for (let i = 0; i < total; i++) {
        const singleTestPlan = {
          ...confirmedPlan,
          tests: [{
            ...confirmedPlan.tests[i],
            user_confirmed: true, user_removed: false,
          }],
        }
        updateLastMessage({ progressLabel: `📊 Running test ${i + 1} of ${total}...` })
        const res = await api.post('/api/ai/execute', { plan: singleTestPlan })
        const batch: TestResult[] = res.data.results || []
        allResults.push(...batch)
        updateLastMessage({ progressLabel: `✅ Test ${i + 1} of ${total} complete.` })
      }

      const results = allResults

      const synthRes = await api.post('/api/ai/synthesize', { question: lastQuestionRef.current, results })
      const answer = synthRes.data

      for (const r of results) {
        outputStore.appendResult({ type: 'ai_assistant', title: r.test_name, data: r.response, status: r.status })
      }

      updateLastMessage({
        loading: false,
        content: `✅ **Analysis complete!** Here are the results:`,
        results,
        answer,
      })

      loadHistory()
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Execution failed'
      updateLastMessage({ loading: false, content: `❌ **Execution Error:** ${detail}` })
    } finally { setExecuting(false) }
  }

  // ── Edit test ───────────────────────────────────────────────────
  const handleEditTest = (test: TestProposal) => {
    setEditingTest({ ...test })
    setEditModalVisible(true)
  }

  const handleSaveEdit = () => {
    if (!editingTest || !currentPlan) return
    const updated = { ...currentPlan, tests: currentPlan.tests.map(t => t.id === editingTest.id ? editingTest : t) }
    setCurrentPlan(updated)
    updateLastMessage({ plan: updated })
    setEditModalVisible(false)
    antMessage.success('Test updated')
  }

  const handleRemoveTest = (testId: string) => {
    if (!currentPlan) return
    const updated = { ...currentPlan, tests: currentPlan.tests.filter(t => t.id !== testId) }
    setCurrentPlan(updated)
    updateLastMessage({ plan: updated })
  }

  // ── Key handlers ────────────────────────────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  // ── Render: Proposal ────────────────────────────────────────────
  const renderProposal = (plan: AnalysisPlan) => (
    <div style={{ marginTop: 8, animation: 'fadeSlideIn 0.4s ease-out' }}>
      <Text strong style={{ fontSize: 16 }}>📋 {plan.plan_name}</Text>
      {plan.notes && <Alert message={plan.notes} type="info" showIcon style={{ marginTop: 8, marginBottom: 8 }} />}
      {plan.tests.map((test, idx) => (
        <Card
          key={test.id}
          size="small"
          style={{ marginTop: 8, borderLeft: '4px solid #005eb8', transition: 'box-shadow 0.2s' }}
          styles={{ body: { padding: 12 } }}
          hoverable
        >
          <Row justify="space-between" align="middle">
            <Col>
              <Space>
                <Text style={{ fontSize: 18 }}>{TEST_ICONS[test.test] || '📊'}</Text>
                <div>
                  <Text strong style={{ fontSize: 14 }}>Test #{idx + 1}: {test.test_name}</Text>
                  {test.fallback_test && <Tag color="gold" style={{ marginLeft: 8 }}>↕ fallback: {test.fallback_test}</Tag>}
                </div>
              </Space>
            </Col>
            <Col>
              <Space size={4}>
                <Tooltip title="Accept"><Button size="small" type="primary" ghost icon={<CheckCircleOutlined />} onClick={() => handleConfirmRun()} /></Tooltip>
                <Tooltip title="Edit"><Button size="small" icon={<EditOutlined />} onClick={() => handleEditTest(test)} /></Tooltip>
                <Tooltip title="Remove"><Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleRemoveTest(test.id)} /></Tooltip>
              </Space>
            </Col>
          </Row>
          <Paragraph style={{ marginTop: 8, marginBottom: 6, color: '#555', fontSize: 13 }}>{test.rationale}</Paragraph>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
            {test.assumptions.map((a, i) => <Tag key={i} color="orange" style={{ fontSize: 11 }}>{a}</Tag>)}
            {test.charts.map((c, i) => <Tag key={i} color="green" style={{ fontSize: 11 }}>📊 {c.type}</Tag>)}
          </div>
        </Card>
      ))}
      {plan.tests.length > 0 && (
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Button
            type="primary"
            size="large"
            icon={<ThunderboltOutlined />}
            onClick={handleConfirmRun}
            loading={executing}
            style={{ minWidth: 260, height: 44, fontSize: 16, borderRadius: 8 }}
          >
            {executing ? 'Running Tests...' : '▶ Confirm & Run All Tests'}
          </Button>
        </div>
      )}
    </div>
  )

  // ── Render: Results ─────────────────────────────────────────────
  const renderResults = (results: TestResult[], answer?: any) => (
    <div style={{ marginTop: 8, animation: 'fadeSlideIn 0.4s ease-out' }}>
      {results.map((r) => (
        <Card
          key={r.test_id}
          size="small"
          style={{ marginTop: 8, borderLeft: `4px solid ${r.status === 'success' ? '#52c41a' : '#ff4d4f'}` }}
          styles={{ body: { padding: 12 } }}
        >
          <Row justify="space-between" align="middle">
            <Col>
              <Space>
                {r.status === 'success'
                  ? <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
                  : <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />}
                <Text strong>{r.test_name}</Text>
                {r.used_fallback && <Tag color="gold">Fallback: {r.fallback_reason}</Tag>}
              </Space>
            </Col>
          </Row>
          {r.error && <Alert message={r.error} type="error" showIcon style={{ marginTop: 6 }} />}
          {r.charts.map((chart, i) => (
            <div key={i} style={{ marginTop: 8 }}>
              <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>{chart.title}</Text>
              {chart.data?.error
                ? <Alert message={`Chart could not be generated: ${chart.data.error}`} type="warning" showIcon />
                : <ChartRenderer data={chart.data} title={chart.title} />
              }
            </div>
          ))}
        </Card>
      ))}

      {answer && (
        <Card style={{ marginTop: 12, background: '#f6f8fa' }} styles={{ body: { padding: 16 } }}>
          <Title level={5} style={{ marginBottom: 8 }}>📝 Summary</Title>
          <Paragraph style={{ fontSize: 15, lineHeight: 1.7 }}>{answer.summary}</Paragraph>

          {answer.detailed_results?.length > 0 && (
            <>
              <Divider />
              <Title level={5} style={{ marginBottom: 8 }}>📋 Detailed Results</Title>
              {answer.detailed_results.map((d: any, i: number) => (
                <Card key={i} size="small" style={{ marginBottom: 8 }} styles={{ body: { padding: 12 } }}>
                  <Text strong>{d.test_name}</Text>
                  <Paragraph style={{ marginTop: 4, marginBottom: 0 }}>{d.apa_result}</Paragraph>
                  {d.effect_size_interpretation && <Text type="secondary" style={{ display: 'block' }}>📐 Effect: {d.effect_size_interpretation}</Text>}
                  {d.clinical_significance && <Text type="secondary" style={{ display: 'block' }}>💡 {d.clinical_significance}</Text>}
                </Card>
              ))}
            </>
          )}

          {answer.limitations && (<> <Divider /> <Alert message="Limitations & Caveats" description={answer.limitations} type="warning" showIcon /> </>)}
          {answer.conclusion && (<> <Divider /> <Paragraph style={{ fontWeight: 500, fontSize: 15 }}>{answer.conclusion}</Paragraph> </>)}
        </Card>
      )}
    </div>
  )

  // ── Edit Modal ──────────────────────────────────────────────────
  const renderEditModal = () => (
    <Modal
      title={`✏️ Edit Test: ${editingTest?.test_name}`}
      open={editModalVisible}
      onOk={handleSaveEdit}
      onCancel={() => setEditModalVisible(false)}
      okText="Save Changes"
      width={520}
      destroyOnClose
    >
      {editingTest && (
        <Space direction="vertical" style={{ width: '100%' }}>
          <div><Text strong>Test Name</Text><Input value={editingTest.test_name} onChange={e => setEditingTest({ ...editingTest, test_name: e.target.value })} /></div>
          <div><Text strong>Rationale</Text><TextArea value={editingTest.rationale} onChange={e => setEditingTest({ ...editingTest, rationale: e.target.value })} rows={2} /></div>
          <div>
            <Text strong>Fallback Test</Text>
            <Select
              value={editingTest.fallback_test || 'none'}
              style={{ width: '100%' }}
              onChange={val => setEditingTest({ ...editingTest, fallback_test: val === 'none' ? null : val })}
              options={[
                { value: 'none', label: 'None' },
                { value: 'mannwhitney', label: 'Mann-Whitney U' },
                { value: 'wilcoxon', label: 'Wilcoxon Signed-Rank' },
                { value: 'kruskalwallis', label: 'Kruskal-Wallis' },
                { value: 'fisher_exact', label: "Fisher's Exact" },
                { value: 'spearman', label: 'Spearman Correlation' },
              ]}
            />
          </div>
        </Space>
      )}
    </Modal>
  )

  // ── Sidebar ─────────────────────────────────────────────────────
  const renderSidebar = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Card size="small" title={<Space><SoundOutlined />Dataset</Space>} styles={{ body: { padding: 12 } }}>
        {datasetLoading ? (
          <Skeleton active paragraph={{ rows: 2 }} />
        ) : datasetInfo ? (
          <div>
            <Text strong style={{ fontSize: 13 }}>{datasetInfo.name}</Text>
            <div style={{ marginTop: 2 }}><Text type="secondary" style={{ fontSize: 12 }}>{datasetInfo.rows} rows × {datasetInfo.cols} cols</Text></div>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>VARIABLES</Text>
              <div style={{ maxHeight: 160, overflow: 'auto', marginTop: 4 }}>
                {datasetInfo.columns?.slice(0, 25).map((c: any) => (
                  <Tag key={c.name} style={{ marginBottom: 2, fontSize: 10, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</Tag>
                ))}
                {(datasetInfo.columns?.length || 0) > 25 && <Text type="secondary" style={{ fontSize: 11 }}>+{datasetInfo.columns.length - 25} more</Text>}
              </div>
            </div>
            <Button size="small" icon={<ReloadOutlined />} onClick={loadDatasetInfo} style={{ marginTop: 8 }}>Refresh</Button>
          </div>
        ) : (
          <div>
            <Empty description="No dataset" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: '8px 0' }} />
            <Dragger beforeUpload={handleUpload} showUploadList={false} accept=".csv,.tsv,.xlsx,.xls,.sav,.dta" style={{ background: '#fafafa' }}>
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text" style={{ fontSize: 12 }}>Click or drag to upload</p>
              <p className="ant-upload-hint" style={{ fontSize: 11 }}>CSV, Excel, SPSS .sav, Stata .dta</p>
            </Dragger>
          </div>
        )}
      </Card>

      <Card size="small" title={<Space><HistoryOutlined />History</Space>} styles={{ body: { padding: 12 } }}>
        {history.length === 0
          ? <Text type="secondary" style={{ fontSize: 12 }}>No past sessions</Text>
          : history.slice().reverse().map((h: any) => (
              <div key={h.id} style={{ padding: '6px 0', cursor: 'pointer', borderBottom: '1px solid #f0f0f0' }}
                   onClick={() => antMessage.info(`Session: ${h.plan_name || h.question?.slice(0, 40)}`)}>
                <Text style={{ fontSize: 12, display: 'block' }}>{h.question?.slice(0, 45)}...</Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {h.timestamp?.slice(0, 10) || ''}
                  {h.success_count !== undefined && ` · ${h.success_count}/${h.test_count} passed`}
                </Text>
              </div>
            ))
        }
      </Card>

      <Card size="small" title={<Space><BulbOutlined />Tips</Space>} styles={{ body: { padding: 12 } }}>
        <ul style={{ margin: 0, paddingLeft: 14, fontSize: 12, lineHeight: 1.8 }}>
          <li>Ask in plain language</li>
          <li>Multiple questions at once work</li>
          <li>Review plan before running</li>
          <li>Edit or remove tests if needed</li>
          <li>Results also go to Output page</li>
        </ul>
      </Card>
    </div>
  )

  // ── Empty state prompts ─────────────────────────────────────────
  const EXAMPLE_QUESTIONS = [
    'Does age differ between male and female patients?',
    'Is there an association between smoking and hypertension?',
    'What factors predict treatment response?',
    'Describe the distribution of age and BMI',
  ]

  // ── Main render ─────────────────────────────────────────────────
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#005eb8',
          borderRadius: 8,
        },
      }}
    >
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
        .chat-bubble {
          transition: all 0.2s ease;
        }
        .chat-bubble:hover {
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
      `}</style>

      <div style={{ height: 'calc(100vh - 130px)', display: 'flex', gap: 16 }}>
        {/* Left: Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '0 4px' }}>
            {messages.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.65 }}>
                <RobotOutlined style={{ fontSize: 48, color: '#005eb8', marginBottom: 16 }} />
                <Title level={4} style={{ color: '#555', margin: 0 }}>AI Statistical Assistant</Title>
                <Paragraph style={{ textAlign: 'center', color: '#888', maxWidth: 420, marginTop: 8 }}>
                  Ask a question about your data in plain language. I'll propose the appropriate
                  statistical tests, run them, and explain the results like a senior biostatistician.
                </Paragraph>
                <Space direction="vertical" style={{ width: 360, marginTop: 8 }}>
                  {EXAMPLE_QUESTIONS.map((q, i) => (
                    <Button key={i} block type="default" style={{ textAlign: 'left', height: 'auto', padding: '8px 12px', whiteSpace: 'normal' }}
                            onClick={() => { setInput(q); inputRef.current?.focus() }}>
                      <Space><BulbOutlined style={{ color: '#005eb8' }} /><Text style={{ fontSize: 13 }}>{q}</Text></Space>
                    </Button>
                  ))}
                </Space>
                {apiKeyMissing && (
                  <Alert message="API key not configured — LLM features won't work" type="warning" showIcon
                         style={{ marginTop: 16, maxWidth: 360 }}
                         description="Set DEEPSEEK_API_KEY in backend/.env and restart." />
                )}
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 12,
                  animation: 'fadeSlideIn 0.3s ease-out',
                }}>
                  <div className="chat-bubble" style={{
                    maxWidth: '88%',
                    background: msg.role === 'user' ? '#e6f4ff' : '#fff',
                    borderRadius: 12,
                    padding: '10px 14px',
                    border: msg.role === 'user' ? '1px solid #bae0ff' : '1px solid #e8e8e8',
                  }}>
                    <div style={{ marginBottom: 6 }}>
                      {msg.role === 'user'
                        ? <Space size={6}><UserOutlined style={{ color: '#005eb8' }} /><Text strong style={{ fontSize: 12, color: '#005eb8' }}>You</Text></Space>
                        : <Space size={6}><RobotOutlined style={{ color: '#005eb8' }} /><Text strong style={{ fontSize: 12, color: '#005eb8' }}>AI Assistant</Text></Space>
                      }
                    </div>

                    {msg.loading
                      ? <LoadingDots label={msg.progressLabel} />
                      : <>
                          {msg.content && <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{msg.content}</Paragraph>}
                          {msg.plan && renderProposal(msg.plan)}
                          {msg.results && msg.results.length > 0 && renderResults(msg.results, msg.answer)}
                        </>
                    }
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          {datasetInfo && (
            <div style={{ borderTop: '1px solid #e8e8e8', padding: '12px 0', marginTop: 8 }}>
              <Row gutter={8}>
                <Col flex="auto">
                  <TextArea
                    ref={inputRef}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask a question about your data... (Enter to send, Shift+Enter for new line)"
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    disabled={sending || executing}
                  />
                </Col>
                <Col>
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={handleSend}
                    loading={sending}
                    disabled={sending || executing || !input.trim()}
                    style={{ height: '100%', minWidth: 80 }}
                  >
                    Send
                  </Button>
                </Col>
              </Row>
            </div>
          )}
        </div>

        {/* Right: Sidebar */}
        <div style={{ width: 275, flexShrink: 0 }}>
          {renderSidebar()}
        </div>

        {/* Edit Modal */}
        {renderEditModal()}
      </div>
    </ConfigProvider>
  )
}

export default AiPage
