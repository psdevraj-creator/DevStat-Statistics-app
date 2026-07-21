import React, { useState, useEffect } from 'react'
import {
  Card, Button, Select, Slider, Space, Typography, message, Spin, Table, Alert, Divider, Row, Col, Statistic, Tooltip,
} from 'antd'
import { PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

const ClusterPage: React.FC = () => {
  const navigate = useNavigate()
  const [columns, setColumns] = useState<string[]>([])
  const [selectedVars, setSelectedVars] = useState<string[]>([])
  const [method, setMethod] = useState<string>('kmeans')
  const [nClusters, setNClusters] = useState(3)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)

  useEffect(() => { loadColumns() }, [])

  const loadColumns = async () => {
    try {
      const res = await datasetApi.columns()
      const cols = (res.data?.columns || res.data || [])
        .filter((c: any) => typeof c === 'string' || c.is_numeric)
        .map((c: any) => typeof c === 'string' ? c : c.name)
      setColumns(cols)
    } catch { message.warning('Failed to load columns') }
  }

  const runCluster = async () => {
    if (selectedVars.length < 2) { message.warning('Select at least 2 numeric variables'); return }
    if (nClusters < 2) { message.warning('Number of clusters must be ≥ 2'); return }

    setLoading(true)
    try {
      const res = await api.post('/api/analysis/cluster', {
        columns: selectedVars,
        method,
        n_clusters: nClusters,
      })
      setResults(res.data)
      outputStore.addEntry('cluster', `Cluster: ${method} (${nClusters} groups)`, res.data)
      message.success('Cluster analysis complete')
    } catch (err: any) {
      message.error('Cluster analysis failed: ' + (err?.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Cluster Analysis</Title>

      <Card title="Configuration" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <div>
            <Text strong>Variables (numeric):</Text>
            <Select mode="multiple" style={{ width: '100%', marginTop: 4 }} placeholder="Select 2+ variables"
              value={selectedVars} onChange={setSelectedVars}
              options={columns.map(c => ({ label: c, value: c }))} />
          </div>
          <Space>
            <div>
              <Text strong>Method:</Text>
              <Select style={{ width: 160, marginLeft: 8 }} value={method} onChange={setMethod}
                options={[
                  { label: 'K-Means', value: 'kmeans' },
                  { label: 'Hierarchical', value: 'hierarchical' },
                ]} />
            </div>
            <div>
              <Text strong>Clusters:</Text>
              <Slider style={{ width: 200, marginLeft: 8 }} min={2} max={10}
                value={nClusters} onChange={v => setNClusters(v)} />
              <Text style={{ marginLeft: 8 }}>{nClusters}</Text>
            </div>
          </Space>
        </Space>
      </Card>

      <Button type="primary" icon={<PlayCircleOutlined />} onClick={runCluster} loading={loading} size="large">
        Run Cluster Analysis
      </Button>

      {loading && <Card style={{ marginTop: 16 }}><div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div></Card>}

      {results && !loading && (
        <Card title="Results" style={{ marginTop: 16 }}
          extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => navigate('/output')}>View Full Results</Button>}>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}><Statistic title="Method" value={results.method} /></Col>
            <Col span={6}><Statistic title="Clusters" value={results.n_clusters} /></Col>
            <Col span={6}><Statistic title="Observations" value={results.n_rows} /></Col>
            <Col span={6}>
              <Statistic title="Silhouette Score" value={results.silhouette_score}
                precision={3}
                valueStyle={{ color: results.silhouette_score >= 0.7 ? '#16a34a' : results.silhouette_score >= 0.5 ? '#ca8a04' : '#dc2626' }}
                suffix={
                  <Tooltip title="> 0.7 = strong structure; 0.5–0.7 = reasonable; < 0.5 = weak — try a different k">
                    <Text type="secondary">{results.silhouette_quality}</Text>
                  </Tooltip>
                } />
            </Col>
          </Row>

          <Divider />
          {results.cluster_sizes && (
            <>
              <Text strong>Cluster Sizes</Text>
              <Table dataSource={results.cluster_sizes}
                columns={[
                  { title: 'Cluster', dataIndex: 'cluster', key: 'cluster' },
                  { title: 'N', dataIndex: 'n', key: 'n' },
                ]} rowKey="cluster" pagination={false} size="small" bordered style={{ marginTop: 8 }} />
            </>
          )}

          {results.centroids && results.centroids.length > 0 && (
            <>
              <Divider />
              <Text strong>Cluster Centroids</Text>
              <Table dataSource={results.centroids}
                columns={[
                  { title: 'Cluster', dataIndex: 'cluster', key: 'cluster' },
                  ...results.columns.map((col: string) => ({
                    title: col, dataIndex: col, key: col,
                    render: (v: number) => v ? v.toFixed(3) : '-',
                  })),
                ]} rowKey="cluster" pagination={false} size="small" bordered style={{ marginTop: 8 }} />
            </>
          )}

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

export default ClusterPage
