import React, { useState, useEffect, useRef } from 'react'
import { Card, Button, Space, Typography, message, Tabs, Input, Select, Tag } from 'antd'
import { PlayCircleOutlined, HistoryOutlined, CopyOutlined } from '@ant-design/icons'
import { api, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const SyntaxPage: React.FC = () => {
  const [code, setCode] = useState('# Enter R code to execute\n# Example:\n# mean(df$age, na.rm = TRUE)\n# table(df$diagnosis)\n')
  const [output, setOutput] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<{ code: string; result: string; time: string }[]>([])
  const [activeTab, setActiveTab] = useState('editor')

  const runCode = async () => {
    if (!code.trim()) return
    setLoading(true)
    setOutput('Running...')

    try {
      const res = await api.post('/api/syntax/run', { code })
      const result = JSON.stringify(res.data, null, 2)
      setOutput(result)

      // Add to history
      setHistory(prev => [{
        code,
        result: result.slice(0, 500),
        time: new Date().toLocaleTimeString(),
      }, ...prev])

      outputStore.addEntry('descriptive', 'R Syntax Run', res.data)
      message.success('Code executed')
    } catch (e: any) {
      const errMsg = e?.response?.data?.detail || e?.message || 'Execution failed'
      setOutput(`Error: ${errMsg}`)
      message.error(errMsg)
    }
    finally { setLoading(false) }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    message.success('Copied')
  }

  const analysisCommands = [
    { label: 'Descriptives', code: 'summary(df)' },
    { label: 'Frequency Table', code: 'table(df$diagnosis)' },
    { label: 'T-Test', code: 't.test(age ~ sex, data=df)' },
    { label: 'ANOVA', code: 'aov(age ~ diagnosis, data=df) |> summary()' },
    { label: 'Chi-square', code: 'chisq.test(table(df$diagnosis, df$stage))' },
    { label: 'Correlation', code: 'cor(df[,c("age","bmi","cholesterol")], use="complete.obs")' },
    { label: 'Linear Model', code: 'lm(age ~ bmi + cholesterol, data=df) |> summary()' },
    { label: 'Logistic', code: 'glm(hypertension ~ age + bmi, data=df, family=binomial) |> summary()' },
    { label: 'Kaplan-Meier', code: 'library(survival); survfit(Surv(survival_months, event_death) ~ treatment, data=df) |> summary()' },
    { label: 'Cox Regression', code: 'library(survival); coxph(Surv(survival_months, event_death) ~ age + sex, data=df) |> summary()' },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Syntax Editor</Title>
        <Text type="secondary">Write and execute R commands — every analysis generates reproducible code</Text>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'editor',
            label: <span><PlayCircleOutlined /> R Editor</span>,
            children: (
              <div style={{ display: 'flex', gap: 16 }}>
                {/* Left: Editor */}
                <div style={{ flex: 1 }}>
                  <Card
                    title="R Code"
                    extra={
                      <Space>
                        <Button type="primary" icon={<PlayCircleOutlined />} onClick={runCode} loading={loading}>
                          Run
                        </Button>
                        <Button icon={<CopyOutlined />} onClick={() => copyToClipboard(code)}>
                          Copy
                        </Button>
                      </Space>
                    }
                  >
                    <Input.TextArea
                      value={code}
                      onChange={e => setCode(e.target.value)}
                      rows={16}
                      style={{
                        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                        fontSize: 13,
                        background: '#1e293b',
                        color: '#e2e8f0',
                        border: 'none',
                        padding: 16,
                        borderRadius: 6,
                      }}
                      placeholder="Enter R code..."
                    />
                  </Card>

                  {/* Quick Templates */}
                  <Card title="Quick Templates" size="small" style={{ marginTop: 12 }}>
                    <Space wrap>
                      {analysisCommands.map(cmd => (
                        <Button
                          key={cmd.label}
                          size="small"
                          onClick={() => {
                            setCode(cmd.code)
                            setActiveTab('editor')
                          }}
                        >
                          {cmd.label}
                        </Button>
                      ))}
                    </Space>
                  </Card>
                </div>

                {/* Right: Output */}
                <div style={{ flex: 1 }}>
                  <Card title="Output">
                    <pre style={{
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                      fontSize: 12,
                      background: '#0f172a',
                      color: '#e2e8f0',
                      padding: 16,
                      borderRadius: 6,
                      minHeight: 400,
                      maxHeight: 600,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      margin: 0,
                    }}>
                      {output || 'Run R code to see output'}
                    </pre>
                  </Card>
                </div>
              </div>
            ),
          },
          {
            key: 'history',
            label: <span><HistoryOutlined /> Command Log</span>,
            children: (
              <Card>
                {history.length === 0 ? (
                  <Text type="secondary">No commands executed yet. Run R code to see history here.</Text>
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {history.map((h, i) => (
                      <Card key={i} size="small" style={{ width: '100%' }}>
                        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Text code style={{ fontSize: 12 }}>{h.code.slice(0, 200)}</Text>
                          <Space>
                            <Tag>{h.time}</Tag>
                            <Button size="small" icon={<CopyOutlined />} onClick={() => copyToClipboard(h.code)} />
                          </Space>
                        </Space>
                        <pre style={{
                          fontSize: 11, background: '#f8fafc', padding: 8,
                          borderRadius: 4, marginTop: 8, maxHeight: 100, overflow: 'auto',
                        }}>
                          {h.result}
                        </pre>
                      </Card>
                    ))}
                  </Space>
                )}
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}

export default SyntaxPage
