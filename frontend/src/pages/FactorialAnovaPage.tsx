import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, Space, Typography, message, Spin, Table, Divider,
  Alert, Collapse,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import { datasetApi, api } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const FactorialAnovaPage: React.FC = () => {
  const navigate = useNavigate()
  const [columns, setColumns] = useState<string[]>([])
  const [dependent, setDependent] = useState<string | undefined>(undefined)
  const [factor1, setFactor1] = useState<string | undefined>(undefined)
  const [factor2, setFactor2] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  useEffect(() => { loadColumns() }, [])

  const loadColumns = async () => {
    try {
      const res = await datasetApi.columns()
      const cols = res.data || []
      setColumns(Array.isArray(cols) ? cols.map((c: any) => typeof c === 'string' ? c : c.name) : [])
    } catch { message.warning('Failed to load columns') }
  }

  const runAnova = async () => {
    if (!dependent) {
      message.warning('Select a dependent variable.')
      return
    }
    if (!factor1 || !factor2) {
      message.warning('Select both factors.')
      return
    }
    setLoading(true)
    setResults(null)
    try {
      const res = await api.post('/api/analysis/anova-twoway', {
        dependent,
        factor1,
        factor2,
      })
      setResults(res.data)
      outputStore.addEntry('anova', 'Factorial ANOVA', res.data)
      message.success('Two-way ANOVA completed.')
    } catch (e: any) {
      message.error(e.response?.data?.detail || e.message || 'Two-way ANOVA failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3} style={{ color: '#005eb8' }}>
        Factorial ANOVA (Two-Way)
      </Title>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <div>
              <Text strong>Outcome Variable:</Text>
              <Select
                showSearch
                style={{ width: 200, marginLeft: 8 }}
                placeholder="Select outcome..."
                value={dependent}
                onChange={setDependent}
                options={columns.map(c => ({ label: c, value: c }))}
              />
            </div>
            <div>
              <Text strong>First grouping (e.g., Treatment):</Text>
              <Select
                showSearch
                style={{ width: 200, marginLeft: 8 }}
                placeholder="Select first grouping..."
                value={factor1}
                onChange={setFactor1}
                options={columns.filter(c => c !== dependent).map(c => ({ label: c, value: c }))}
              />
            </div>
            <div>
              <Text strong>Second grouping (e.g., Gender / Stage):</Text>
              <Select
                showSearch
                style={{ width: 200, marginLeft: 8 }}
                placeholder="Select second grouping..."
                value={factor2}
                onChange={setFactor2}
                options={columns.filter(c => c !== dependent && c !== factor1).map(c => ({ label: c, value: c }))}
              />
            </div>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={runAnova}
              loading={loading}
            >
              Run Two-Way ANOVA
            </Button>
          </Space>
        </Space>
      </Card>

      {loading && <Spin style={{ display: 'block', margin: '40px auto' }} />}

      {results && (
        <Card extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
          {/* Interpretation */}
          {results.interpretation && (
            <Alert
              type={results.error ? 'error' : 'info'}
              message="Interpretation"
              description={results.interpretation}
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Error */}
          {results.error && (
            <Alert type="error" message="Error" description={results.error} style={{ marginBottom: 16 }} />
          )}

          {/* ANOVA Table */}
          {results.anova_table && (
            <>
              <Title level={5}>ANOVA Table</Title>
              <Table
                dataSource={results.anova_table}
                columns={[
                  { title: 'Source', dataIndex: 'source', key: 'source' },
                  { title: 'df', dataIndex: 'df', key: 'df' },
                  { title: 'Sum Sq', dataIndex: 'sum_sq', key: 'sum_sq' },
                  { title: 'Mean Sq', dataIndex: 'mean_sq', key: 'mean_sq' },
                  { title: 'F', dataIndex: 'f', key: 'f' },
                  {
                    title: 'p',
                    dataIndex: 'p_value',
                    key: 'p_value',
                    render: (v: number) => (
                      <span style={{ color: v < 0.05 ? '#cf1322' : '#333', fontWeight: v < 0.05 ? 'bold' : 'normal' }}>
                        {v}
                      </span>
                    ),
                  },
                ]}
                pagination={false}
                size="small"
              />
              <Divider />
            </>
          )}

          {/* Effect Sizes */}
          {results.effect_sizes && (
            <>
              <Title level={5}>Effect Sizes (Partial η²)</Title>
              <Table
                dataSource={Object.entries(results.effect_sizes).map(([key, val]: [string, any]) => ({
                  key,
                  source: key,
                  partial_eta_squared: val.partial_eta_squared,
                  interpretation: val.interpretation,
                }))}
                columns={[
                  { title: 'Source', dataIndex: 'source', key: 'source' },
                  { title: 'Partial η²', dataIndex: 'partial_eta_squared', key: 'partial_eta_squared' },
                  { title: 'Interpretation', dataIndex: 'interpretation', key: 'interpretation' },
                ]}
                pagination={false}
                size="small"
              />
              <Divider />
            </>
          )}

          {/* Descriptives - Marginal Means */}
          {results.descriptives?.marginal && (
            <>
              <Title level={5}>Marginal Means</Title>
              {Object.entries(results.descriptives.marginal).map(([factor, levels]: [string, any]) => (
                <div key={factor} style={{ marginBottom: 12 }}>
                  <Text strong>Factor: {factor}</Text>
                  <Table
                    dataSource={Object.entries(levels).map(([level, stats]: [string, any]) => ({
                      key: level,
                      level,
                      n: stats.n,
                      mean: stats.mean,
                      sd: stats.sd,
                      ci_lower: stats.ci_lower,
                      ci_upper: stats.ci_upper,
                    }))}
                    columns={[
                      { title: 'Level', dataIndex: 'level', key: 'level' },
                      { title: 'N', dataIndex: 'n', key: 'n' },
                      { title: 'Mean', dataIndex: 'mean', key: 'mean' },
                      { title: 'SD', dataIndex: 'sd', key: 'sd' },
                      { title: '95% CI Lower', dataIndex: 'ci_lower', key: 'ci_lower' },
                      { title: '95% CI Upper', dataIndex: 'ci_upper', key: 'ci_upper' },
                    ]}
                    pagination={false}
                    size="small"
                  />
                </div>
              ))}
              <Divider />
            </>
          )}

          {/* Cell Means */}
          {results.descriptives?.cell && (
            <>
              <Title level={5}>Cell Means</Title>
              <Table
                dataSource={Object.entries(results.descriptives.cell).flatMap(([f1, f2map]: [string, any]) =>
                  Object.entries(f2map).map(([f2, stats]: [string, any]) => ({
                    key: `${f1}_${f2}`,
                    factor1: f1,
                    factor2: f2,
                    n: stats.n,
                    mean: stats.mean,
                    sd: stats.sd,
                  }))
                )}
                columns={[
                  { title: results.factors?.factor1 || 'Factor 1', dataIndex: 'factor1', key: 'factor1' },
                  { title: results.factors?.factor2 || 'Factor 2', dataIndex: 'factor2', key: 'factor2' },
                  { title: 'N', dataIndex: 'n', key: 'n' },
                  { title: 'Mean', dataIndex: 'mean', key: 'mean' },
                  { title: 'SD', dataIndex: 'sd', key: 'sd' },
                ]}
                pagination={false}
                size="small"
              />
            </>
          )}
        </Card>
      )}
    </div>
  )
}

export default FactorialAnovaPage
