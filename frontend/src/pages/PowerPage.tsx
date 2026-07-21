import React, { useState } from 'react'
import {
  Card, Button, Select, InputNumber, Space, Typography, message, Spin, Table, Alert, Divider, Radio,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { powerApi } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const TEST_TYPES = [
  { label: 'Independent t-test (2 groups)', value: 'ttest' },
  { label: 'Paired t-test (before/after)', value: 'ttest_paired' },
  { label: 'ANOVA (3+ groups)', value: 'anova' },
  { label: 'Chi-square (categorical)', value: 'chisquare' },
]

const QUESTIONS = [
  { key: 'n', label: 'How many patients do I need?', desc: 'Calculate required sample size from expected effect and desired power' },
  { key: 'power', label: 'Is my study adequately powered?', desc: 'Calculate statistical power from sample size and expected effect' },
  { key: 'effect_size', label: 'What effect size can I detect?', desc: 'Calculate the smallest detectable effect given sample size and power' },
]

const PowerPage: React.FC = () => {
  const navigate = useNavigate()
  const [test, setTest] = useState('ttest')
  const [question, setQuestion] = useState<string>('n')
  const [effectSize, setEffectSize] = useState<number | undefined>(0.5)
  const [sampleSize, setSampleSize] = useState<number | undefined>(100)
  const [desiredPower, setDesiredPower] = useState<number | undefined>(0.8)
  const [alpha, setAlpha] = useState(0.05)
  const [k, setK] = useState<number | undefined>(3)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  const runPower = async () => {
    if (question === 'power' && !effectSize) { message.warning('Enter the expected effect size'); return }
    if (question === 'power' && !sampleSize) { message.warning('Enter your planned sample size'); return }
    if (question === 'n' && !effectSize) { message.warning('Enter the expected effect size'); return }
    if (question === 'n' && !desiredPower) { message.warning('Enter your desired statistical power'); return }
    if (question === 'effect_size' && !sampleSize) { message.warning('Enter your planned sample size'); return }
    if (question === 'effect_size' && !desiredPower) { message.warning('Enter your desired statistical power'); return }
    if ((test === 'anova' || test === 'chisquare') && !k) { message.warning('Enter number of groups (ANOVA) or degrees of freedom (chi-square)'); return }

    const param = question as 'n' | 'power' | 'effect_size'

    setLoading(true)
    try {
      const res = await powerApi.run({
        test,
        ...(param === 'power' ? { effect_size: effectSize, n: sampleSize, alpha } : {}),
        ...(param === 'n' ? { effect_size: effectSize, power: desiredPower, alpha } : {}),
        ...(param === 'effect_size' ? { n: sampleSize, power: desiredPower, alpha } : {}),
        ...((test === 'anova' || test === 'chisquare') ? { k } : {}),
      })
      setResults(res.data)
      const qLabel = QUESTIONS.find(q => q.key === question)?.label || question
      outputStore.addEntry('power', `Power: ${qLabel} — ${TEST_TYPES.find(t => t.value === test)?.label}`, res.data)
      message.success('Power analysis complete')
    } catch (err: any) {
      message.error('Power analysis failed: ' + (err?.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Power Analysis</Title>

      <Card title="What do you want to know?" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Radio.Group value={question} onChange={e => { setQuestion(e.target.value); setResults(null) }}
            style={{ width: '100%' }}>
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              {QUESTIONS.map(q => (
                <div key={q.key}
                  style={{
                    padding: '10px 16px', border: `1px solid ${question === q.key ? '#005eb8' : '#d9d9d9'}`,
                    borderRadius: 6, cursor: 'pointer', background: question === q.key ? '#f0f7ff' : '#fff',
                    transition: 'all 0.2s',
                  }}
                  onClick={() => { setQuestion(q.key); setResults(null) }}>
                  <Radio value={q.key}>
                    <Text strong style={{ fontSize: 14 }}>{q.label}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>{q.desc}</Text>
                  </Radio>
                </div>
              ))}
            </Space>
          </Radio.Group>
        </Space>
      </Card>

      <Card title="Parameters" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space><Text style={{ width: 160 }}>Test type:</Text>
            <Select style={{ width: 300 }} value={test} onChange={v => { setTest(v); setResults(null) }} options={TEST_TYPES} /></Space>

          <Divider style={{ margin: '4px 0' }} />

          {(question === 'power' || question === 'n') && (
            <Space>
              <Text style={{ width: 160 }}>Expected effect size:</Text>
              <InputNumber style={{ width: 130 }} min={0.01} max={5} step={0.1}
                value={effectSize} onChange={v => setEffectSize(v ?? undefined)} />
              <Text type="secondary" style={{ fontSize: 11 }}>Cohen's d (small=0.2, medium=0.5, large=0.8)</Text>
            </Space>
          )}
          {(question === 'power' || question === 'effect_size') && (
            <Space>
              <Text style={{ width: 160 }}>Sample size (N):</Text>
              <InputNumber style={{ width: 130 }} min={2} step={10}
                value={sampleSize} onChange={v => setSampleSize(v ?? undefined)} />
            </Space>
          )}
          {(question === 'n' || question === 'effect_size') && (
            <Space>
              <Text style={{ width: 160 }}>Desired statistical power:</Text>
              <InputNumber style={{ width: 130 }} min={0.01} max={0.99} step={0.05}
                value={desiredPower} onChange={v => setDesiredPower(v ?? undefined)} />
              <Text type="secondary" style={{ fontSize: 11 }}>Typically 0.80 (80%)</Text>
            </Space>
          )}
          <Space>
            <Text style={{ width: 160 }}>Significance level (α):</Text>
            <InputNumber style={{ width: 130 }} min={0.001} max={0.5} step={0.01}
              value={alpha} onChange={v => setAlpha(v ?? 0.05)} />
            <Text type="secondary" style={{ fontSize: 11 }}>Typically 0.05</Text>
          </Space>
          {(test === 'anova' || test === 'chisquare') && (
            <Space>
              <Text style={{ width: 160 }}>{test === 'anova' ? 'Number of groups (k):' : 'Degrees of freedom (df):'}</Text>
              <InputNumber style={{ width: 130 }} min={2} max={100} step={1}
                value={k} onChange={v => setK(v ?? undefined)} />
            </Space>
          )}
        </Space>
      </Card>

      <Button type="primary" icon={<PlayCircleOutlined />} onClick={runPower} loading={loading} size="large">
        Calculate
      </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div></Card>}

      {results && !loading && (
        <Card title="Results" style={{ marginTop: 16, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}
          extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => navigate('/output')}>View Full Results</Button>}>
          <Table
            dataSource={[
              { metric: 'Test', value: TEST_TYPES.find(t => t.value === results.test)?.label || results.test },
              { metric: 'Question', value: QUESTIONS.find(q => q.key === results.parameter_type)?.label || results.parameter_type },
              { metric: 'Alpha (α)', value: results.alpha },
              ...(results.effect_size !== undefined ? [{ metric: 'Effect size', value: results.effect_size }] : []),
              ...(results.n !== undefined ? [{ metric: 'Sample size (N)', value: results.n }] : []),
              ...(results.power !== undefined ? [{ metric: 'Power', value: results.power }] : []),
              ...(results.k !== undefined ? [{ metric: results.test === 'anova' ? 'Groups (k)' : 'df', value: results.k }] : []),
            ]}
            columns={[
              { title: 'Parameter', dataIndex: 'metric', key: 'metric' },
              { title: 'Value', dataIndex: 'value', key: 'value' },
            ]}
            rowKey="metric" pagination={false} size="small" bordered
          />
          {results.interpretation && (
            <Alert type="info" message="Interpretation"
              description={results.interpretation}
              style={{ marginTop: 16, background: '#f0f7ff', border: '1px solid #bae0ff' }} />
          )}
        </Card>
      )}
    </div>
  )
}

export default PowerPage