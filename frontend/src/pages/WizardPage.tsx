import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Space, Typography, Input, Tag, Alert, message, Spin, Divider,
} from 'antd'
import {
  QuestionCircleOutlined, RightCircleOutlined, BulbOutlined,
  ArrowLeftOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { api } from '../api/client'

const { Text, Title, Paragraph } = Typography
const { TextArea } = Input

// ── Types ─────────────────────────────────────────────────────────────

interface WizardState {
  current_node: string
  answers: Record<string, string>
  done?: boolean
}

interface WizardRecommendation {
  test_name: string
  alternative: string
  graphs: string[]
  assumptions: string[]
  module: string
  explanation: string
  prefill_params: Record<string, any>
}

interface WizardResponse {
  response: {
    question?: string
    text?: string
    type?: string
    options?: Record<string, string>
    next_node?: string
    result?: boolean
    test_name?: string
    error?: string
  }
  state: WizardState
  recommendation?: WizardRecommendation | null
}

// ── Chat message type ─────────────────────────────────────────────────

interface ChatMessage {
  role: 'user' | 'wizard'
  text: string
  options?: Record<string, string>
  recommendation?: WizardRecommendation | null
  error?: boolean
}

// ── Page component ────────────────────────────────────────────────────

const WizardPage: React.FC = () => {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<WizardState | null>(null)
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [started, setStarted] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Send query to backend ──────────────────────────────────────────

  const sendQuery = async (text: string) => {
    if (!text.trim()) return

    setLoading(true)

    // Add the user message
    const userMsg: ChatMessage = { role: 'user', text: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInputText('')

    try {
      const res = await api.post('/api/wizard/query', {
        text: text.trim(),
        state: state,
      })
      const data: WizardResponse = res.data
      setState(data.state)

      const resp = data.response

      // Check for error
      if (resp.error) {
        setMessages(prev => [
          ...prev,
          { role: 'wizard', text: resp.error || 'Something went wrong.', error: true },
        ])
        return
      }

      // If we have a result (leaf node reached)
      if (resp.result && data.recommendation) {
        setMessages(prev => [
          ...prev,
          {
            role: 'wizard',
            text: data.recommendation.explanation,
            recommendation: data.recommendation,
          },
        ])
        return
      }

      // Otherwise it's a question with options
      if (resp.text && resp.options) {
        setMessages(prev => [
          ...prev,
          {
            role: 'wizard',
            text: resp.text || '',
            options: resp.options,
          },
        ])
      } else if (resp.text) {
        // Just a text response (no options)
        setMessages(prev => [
          ...prev,
          { role: 'wizard', text: resp.text || '' },
        ])
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      const errMsg = typeof detail === 'string' ? detail : (err.message || 'Connection failed')
      setMessages(prev => [
        ...prev,
        { role: 'wizard', text: `Error: ${errMsg}`, error: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  // ── Start wizard ───────────────────────────────────────────────────

  const startWizard = () => {
    setStarted(true)
    setMessages([
      {
        role: 'wizard',
        text: 'Hello! I can help you choose the right statistical test for your analysis.\n\nDescribe what you want to do, or type "help" to start the structured questionnaire.',
      },
    ])
    setState(null)
  }

  // ── Handle option button click (structured Q&A) ────────────────────

  const handleOptionClick = (key: string, label: string) => {
    sendQuery(key)
  }

  // ── Handle free-text submit ────────────────────────────────────────

  const handleTextSubmit = () => {
    if (inputText.trim()) {
      sendQuery(inputText.trim())
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleTextSubmit()
    }
  }

  // ── Reset wizard ──────────────────────────────────────────────────

  const resetWizard = () => {
    setMessages([])
    setState(null)
    setStarted(false)
    setInputText('')
  }

  // ── Navigate to recommended module ─────────────────────────────────

  const openModule = (module: string) => {
    // Map API module paths to frontend routes
    const routeMap: Record<string, string> = {
      '/api/analysis/ttest': '/analyze/compare',
      '/api/analysis/anova': '/analyze/compare',
      '/api/analysis/chisquare': '/analyze/compare',
      '/api/analysis/correlation': '/analyze/correlation',
      '/api/analysis/partial-correlation': '/analyze/correlation',
      '/api/analysis/linear-regression': '/analyze/regression',
      '/api/analysis/logistic-regression': '/analyze/regression',
      '/api/analysis/mixed-model': '/analyze/regression',
      '/api/analysis/kaplan-meier': '/survival',
      '/api/analysis/cox-regression': '/survival',
      '/api/analysis/diagnostic': '/analyze/diagnostic',
      '/api/analysis/factor': '/analyze/factor',
      '/api/analysis/reliability': '/analyze/factor',
      '/api/analysis/cluster': '/analyze/factor',
      '/api/analysis/power': '/analyze/descriptive',
      '/api/analysis/descriptive': '/analyze/descriptive',
      '/api/analysis/explore': '/analyze/descriptive',
    }
    const target = routeMap[module] || '/analyze/descriptive'
    navigate(target)
  }

  // ── Render a single chat message ──────────────────────────────────

  const renderMessage = (msg: ChatMessage, idx: number) => {
    const isUser = msg.role === 'user'

    return (
      <div key={idx} style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        {/* Message bubble */}
        <div
          style={{
            maxWidth: '80%',
            padding: '12px 16px',
            borderRadius: 12,
            background: isUser ? '#005eb8' : '#f0f2f5',
            color: isUser ? '#fff' : '#262626',
            borderBottomRightRadius: isUser ? 4 : 12,
            borderBottomLeftRadius: isUser ? 12 : 4,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          }}
        >
          <Text style={{ color: isUser ? '#fff' : '#262626', fontSize: 14, lineHeight: 1.6 }}>
            {msg.text}
          </Text>
        </div>

        {/* Options buttons (wizard only) */}
        {msg.options && !msg.error && (
          <div style={{ marginTop: 10, width: '100%' }}>
            <Space wrap size={[8, 8]}>
              {Object.entries(msg.options).map(([key, label]) => (
                <Button
                  key={key}
                  size="small"
                  icon={<RightCircleOutlined />}
                  onClick={() => handleOptionClick(key, label)}
                  style={{
                    borderRadius: 20,
                    borderColor: '#005eb8',
                    color: '#005eb8',
                  }}
                >
                  {label}
                </Button>
              ))}
            </Space>
          </div>
        )}

        {/* Recommendation card */}
        {msg.recommendation && (
          <Card
            style={{
              marginTop: 12,
              width: '100%',
              borderLeft: '4px solid #005eb8',
              borderRadius: 8,
              background: '#fafafa',
            }}
            size="small"
          >
            {/* Test name as title */}
            <Title level={5} style={{ color: '#005eb8', marginBottom: 12 }}>
              <BulbOutlined style={{ marginRight: 8 }} />
              {msg.recommendation.test_name}
            </Title>

            {/* Explanation in blue info box */}
            <Alert
              type="info"
              showIcon
              icon={<BulbOutlined />}
              message="Explanation"
              description={
                <div style={{ whiteSpace: 'pre-wrap' }}>
                  {msg.recommendation.explanation.replace(/\*\*/g, '')}
                </div>
              }
              style={{ marginBottom: 12, background: '#e6f7ff', border: '1px solid #91d5ff' }}
            />

            {/* Alternative test */}
            {msg.recommendation.alternative && (
              <div style={{ marginBottom: 10 }}>
                <Text strong style={{ fontSize: 13 }}>Alternative test: </Text>
                <Tag color="orange">{msg.recommendation.alternative}</Tag>
              </div>
            )}

            {/* Graphs to generate */}
            {msg.recommendation.graphs.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <Text strong style={{ fontSize: 13 }}>Recommended graphs: </Text>
                <div style={{ marginTop: 4 }}>
                  <Space wrap size={[4, 4]}>
                    {msg.recommendation.graphs.map((g, gi) => (
                      <Tag key={gi} color="blue">{g}</Tag>
                    ))}
                  </Space>
                </div>
              </div>
            )}

            {/* Assumptions to check */}
            {msg.recommendation.assumptions.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <Text strong style={{ fontSize: 13 }}>Assumptions to check: </Text>
                <div style={{ marginTop: 4 }}>
                  <Space wrap size={[4, 4]}>
                    {msg.recommendation.assumptions.map((a, ai) => (
                      <Tag key={ai} color="warning">{a}</Tag>
                    ))}
                  </Space>
                </div>
              </div>
            )}

            {/* Open Module button */}
            <Divider style={{ margin: '8px 0' }} />
            <Button
              type="primary"
              icon={<RightCircleOutlined />}
              onClick={() => openModule(msg.recommendation!.module)}
              block
            >
              Open Module — {msg.recommendation.test_name}
            </Button>
          </Card>
        )}

        {/* Error alert */}
        {msg.error && (
          <Alert
            type="error"
            showIcon
            message={msg.text}
            style={{ marginTop: 8, width: '100%' }}
          />
        )}
      </div>
    )
  }

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ color: '#1a1a2e', margin: 0 }}>
            <QuestionCircleOutlined style={{ marginRight: 10, color: '#005eb8' }} />
            Help Wizard
          </Title>
          <Text type="secondary">
            Answer a few questions to find the right statistical test.
          </Text>
        </div>
        {started && (
          <Button icon={<ReloadOutlined />} onClick={resetWizard} size="small">
            Start Over
          </Button>
        )}
      </div>

      {!started ? (
        /* ── Welcome / start screen ── */
        <Card>
          <div style={{ textAlign: 'center', padding: '32px 16px' }}>
            <QuestionCircleOutlined style={{ fontSize: 48, color: '#005eb8', marginBottom: 16 }} />
            <Title level={4} style={{ color: '#1a1a2e' }}>
              Which statistical test should I use?
            </Title>
            <Paragraph type="secondary" style={{ maxWidth: 500, margin: '0 auto 24px' }}>
              This wizard will guide you step-by-step to the right statistical test
              for your data and research question. No prior statistical knowledge required.
            </Paragraph>
            <Button type="primary" size="large" onClick={startWizard} icon={<RightCircleOutlined />}>
              Start the Wizard
            </Button>
          </div>
        </Card>
      ) : (
        /* ── Chat interface ── */
        <Card
          style={{
            borderRadius: 12,
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            minHeight: 400,
            display: 'flex',
            flexDirection: 'column',
          }}
          styles={{
            body: {
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              padding: 16,
            }
          }}
        >
          {/* Messages container */}
          <div style={{ flex: 1, overflowY: 'auto', marginBottom: 16, minHeight: 300 }}>
            {messages.length === 1 && (
              <div style={{ textAlign: 'center', margin: '8px 0 16px' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Tip: Type "compare two groups", "correlation", "survival", or just "help" below.
                </Text>
              </div>
            )}
            {messages.map((msg, idx) => renderMessage(msg, idx))}
            {loading && (
              <div style={{ textAlign: 'center', padding: 16 }}>
                <Spin tip="Thinking..." />
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <TextArea
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your answer or describe your analysis..."
              autoSize={{ minRows: 1, maxRows: 4 }}
              style={{ borderRadius: 8, flex: 1 }}
              disabled={loading}
            />
            <Button
              type="primary"
              icon={<RightCircleOutlined />}
              onClick={handleTextSubmit}
              loading={loading}
              disabled={!inputText.trim()}
              style={{ borderRadius: 8, height: 40 }}
            >
              Send
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}

export default WizardPage
