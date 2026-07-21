import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, InputNumber, Space, Typography, message, Spin, Table, Divider,
  Tabs, Alert, Collapse,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import EligibilityAlert from '../components/EligibilityAlert'
import { useEligibilityCheck } from '../hooks/useEligibility'
import { datasetApi, api } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const FactorPage: React.FC = () => {
  const navigate = useNavigate()
  const [columns, setColumns] = useState<string[]>([])
  const [selectedCols, setSelectedCols] = useState<string[]>([])
  const [nFactors, setNFactors] = useState<number>(2)
  const [rotation, setRotation] = useState<string>('varimax')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [tab, setTab] = useState<string>('factor')

  const eligParams = useMemo(() => ({
    analysis: tab === 'factor' ? 'factor' : 'reliability',
    n_vars: selectedCols.length,
    n_items: selectedCols.length,
  }), [tab, selectedCols])
  const eligibility = useEligibilityCheck(selectedCols.length >= 2 ? eligParams : null)

  useEffect(() => { loadColumns() }, [])

  const loadColumns = async () => {
    try {
      const res = await datasetApi.columns()
      const cols = res.data || []
      // Filter to numeric columns only
      const numericCols = cols.filter((c: any) => {
        if (typeof c === 'string') return true
        return c.is_numeric
      })
      setColumns(Array.isArray(numericCols) ? numericCols.map((c: any) => typeof c === 'string' ? c : c.name) : [])
    } catch { message.warning('Failed to load columns') }
  }

  const runFactorAnalysis = async () => {
    if (selectedCols.length < 2) {
      message.warning('Select at least 2 variables.')
      return
    }
    setLoading(true)
    setResults(null)
    try {
      const res = await api.post('/api/analysis/factor', {
        columns: selectedCols,
        n_factors: nFactors,
        rotation: rotation,
      })
      setResults(res.data)
      outputStore.addEntry('factor', 'Factor Analysis', res.data)
      message.success('Factor analysis completed.')
    } catch (e: any) {
      message.error(e.response?.data?.detail || e.message || 'Factor analysis failed.')
    } finally {
      setLoading(false)
    }
  }

  const runReliability = async () => {
    if (selectedCols.length < 2) {
      message.warning('Select at least 2 variables.')
      return
    }
    setLoading(true)
    setResults(null)
    try {
      const res = await api.post('/api/analysis/reliability', {
        columns: selectedCols,
      })
      setResults(res.data)
      outputStore.addEntry('reliability', 'Reliability Analysis (Cronbach Alpha)', res.data)
      message.success('Reliability analysis completed.')
    } catch (e: any) {
      message.error(e.response?.data?.detail || e.message || 'Reliability analysis failed.')
    } finally {
      setLoading(false)
    }
  }

  const rotationOptions = [
    { label: 'Varimax — simplest structure', value: 'varimax' },
    { label: 'Promax — allows correlated factors', value: 'promax' },
    { label: 'Oblimin — similar to Promax', value: 'oblimin' },
    { label: 'Quartimax — simplifies variables', value: 'quartimax' },
    { label: 'None — unrotated', value: 'none' },
  ]

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3} style={{ color: '#005eb8' }}>
        Factor Analysis &amp; Reliability
      </Title>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>Variables:</Text>
            <Select
              mode="multiple"
              style={{ width: '100%', marginTop: 4 }}
              placeholder="Select numeric variables..."
              value={selectedCols}
              onChange={setSelectedCols}
              options={columns.map(c => ({ label: c, value: c }))}
            />
          </div>

          <Tabs activeKey={tab} onChange={setTab} items={[
            {
              key: 'factor',
              label: 'Factor Analysis',
              children: (
                <Space>
                  <div>
                    <Text strong>Number of Factors:</Text>
                    <InputNumber
                      min={1}
                      max={selectedCols.length || 10}
                      value={nFactors}
                      onChange={v => setNFactors(v || 1)}
                      style={{ marginLeft: 8, width: 80 }}
                    />
                  </div>
                  <div>
                    <Text strong>Rotation:</Text>
                    <Select
                      value={rotation}
                      onChange={setRotation}
                      options={rotationOptions}
                      style={{ marginLeft: 8, width: 140 }}
                    />
                  </div>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={runFactorAnalysis}
                    loading={loading}
                  >
                    Run Factor Analysis
                  </Button>
                  <EligibilityAlert result={eligibility} />
                </Space>
              ),
            },
            {
              key: 'reliability',
              label: 'Reliability (Cronbach\'s α)',
              children: (
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={runReliability}
                  loading={loading}
                >
                  Compute Cronbach's Alpha
                </Button>
              ),
            },
          ]} />
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

          {/* KMO & Bartlett */}
          {results.kmo && (
            <>
              <Title level={5}>KMO and Bartlett's Test</Title>
              <Table
                dataSource={[
                  {
                    key: 'kmo',
                    measure: 'KMO Measure of Sampling Adequacy',
                    value: results.kmo.model,
                    interpretation: results.kmo.interpretation,
                  },
                  {
                    key: 'bartlett',
                    measure: "Bartlett's Test of Sphericity",
                    value: `χ² = ${results.bartlett?.chi2}, df = ${results.bartlett?.df}, p = ${results.bartlett?.p_value}`,
                    interpretation: results.bartlett?.p_value < 0.05 ? 'Significant (data suitable)' : 'Not significant',
                  },
                ]}
                columns={[
                  { title: 'Measure', dataIndex: 'measure', key: 'measure' },
                  { title: 'Value', dataIndex: 'value', key: 'value' },
                  { title: 'Interpretation', dataIndex: 'interpretation', key: 'interpretation' },
                ]}
                pagination={false}
                size="small"
              />
              <Divider />
            </>
          )}

          {/* Variance Explained */}
          {results.variance_explained && (
            <>
              <Title level={5}>Variance Explained</Title>
              {(() => {
                const ve = results.variance_explained.map((r: any) => ({
                  factor: r.factor,
                  eigenvalue: r.ss_loadings ?? r.eigenvalue,
                  variance_pct: r.proportion_var != null ? Number((r.proportion_var * 100).toFixed(2)) : r.variance_pct,
                  cumulative_pct: r.cumulative_var != null ? Number((r.cumulative_var * 100).toFixed(2)) : r.cumulative_pct,
                }))
                return (
                  <Table
                    dataSource={ve}
                    columns={[
                      { title: 'Factor', dataIndex: 'factor', key: 'factor' },
                      { title: 'Eigenvalue', dataIndex: 'eigenvalue', key: 'eigenvalue' },
                      { title: 'Variance %', dataIndex: 'variance_pct', key: 'variance_pct' },
                      { title: 'Cumulative %', dataIndex: 'cumulative_pct', key: 'cumulative_pct' },
                    ]}
                    pagination={false}
                    size="small"
                  />
                )
              })()}
              <Divider />
            </>
          )}

          {/* Loadings */}
          {results.loadings && (
            <>
              <Title level={5}>Factor Loadings</Title>
              <Table
                dataSource={results.loadings}
                columns={[
                  { title: 'Variable', dataIndex: 'variable', key: 'variable' },
                  ...Array.from({ length: results.n_factors || 2 }, (_, i) => ({
                    title: `Factor ${i + 1}`,
                    dataIndex: `factor_${i + 1}`,
                    key: `factor_${i + 1}`,
                    render: (v: number) => (
                      <span style={{ fontWeight: Math.abs(v) >= 0.4 ? 'bold' : 'normal', color: Math.abs(v) >= 0.7 ? '#005eb8' : '#333' }}>
                        {v}
                      </span>
                    ),
                  })),
                ]}
                pagination={false}
                size="small"
              />
              <Divider />
            </>
          )}

          {/* Communalities */}
          {results.communalities && (
            <>
              <Title level={5}>Communalities</Title>
              <Table
                dataSource={results.communalities}
                columns={[
                  { title: 'Variable', dataIndex: 'variable', key: 'variable' },
                  { title: 'Communality', dataIndex: 'communality', key: 'communality' },
                ]}
                pagination={false}
                size="small"
              />
              <Divider />
            </>
          )}

          {/* Reliability: Cronbach's Alpha */}
          {results.alpha !== undefined && (
            <>
              <Title level={5}>Cronbach's Alpha</Title>
              <Table
                dataSource={[
                  {
                    key: 'alpha',
                    measure: 'Cronbach\'s Alpha',
                    value: results.alpha,
                    ci: results.alpha_ci ? `[${results.alpha_ci[0]}, ${results.alpha_ci[1]}]` : 'N/A',
                    items: results.n_items,
                    n: results.n_observations ?? results.n,
                  },
                ]}
                columns={[
                  { title: 'Alpha', dataIndex: 'value', key: 'value' },
                  { title: '95% CI', dataIndex: 'ci', key: 'ci' },
                  { title: 'Items', dataIndex: 'items', key: 'items' },
                  { title: 'N', dataIndex: 'n', key: 'n' },
                ]}
                pagination={false}
                size="small"
              />
              <Divider />
            </>
          )}

          {/* Item Statistics */}
          {results.item_statistics && (
            <>
              <Title level={5}>Item Statistics</Title>
              <Table
                dataSource={results.item_statistics}
                columns={[
                  { title: 'Item', dataIndex: 'item', key: 'item' },
                  { title: 'Mean', dataIndex: 'mean', key: 'mean' },
                  { title: 'SD', dataIndex: 'sd', key: 'sd' },
                  { title: 'Item-Total r', dataIndex: 'item_total_correlation', key: 'item_total_correlation' },
                  { title: 'Alpha if Deleted', dataIndex: 'alpha_if_deleted', key: 'alpha_if_deleted' },
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

export default FactorPage
