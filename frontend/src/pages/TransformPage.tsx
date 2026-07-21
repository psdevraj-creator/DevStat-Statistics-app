import React, { useState, useEffect } from 'react'
import {
  Card, Button, Space, Typography, Select, Input, InputNumber, message, Tabs,
  Radio, Tag, Divider, Table, Switch, Alert, Modal, Form, Descriptions,
} from 'antd'
import {
  SortAscendingOutlined, NumberOutlined, FilterOutlined,
  OrderedListOutlined, PartitionOutlined, PercentageOutlined,
  GroupOutlined, PlusOutlined, DeleteOutlined,
} from '@ant-design/icons'
import { api, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'

const { Text, Title } = Typography

// ── Data Transformation Page ──────────────────────────────────────────────

const TransformPage: React.FC = () => {
  const [columns, setColumns] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  // Load column list on mount
  useEffect(() => {
    loadColumns()
  }, [])

  const loadColumns = async () => {
    try {
      const res = await datasetApi.info()
      const colNames = (res.data?.columns || []).map((c: any) => ({ label: c.name, value: c.name }))
      setColumns(colNames)
    } catch {
      setColumns([])
    }
  }

  // ── Rank ───────────────────────────────────────────────────────────────
  const [rankVars, setRankVars] = useState<string[]>([])
  const [rankType, setRankType] = useState<string>('rank')
  const [rankDir, setRankDir] = useState<string>('asc')
  const [rankNTiles, setRankNTiles] = useState(4)
  const [rankResult, setRankResult] = useState<any>(null)

  const doRank = async () => {
    if (!rankVars.length) { message.warning('Select at least one variable'); return }
    setLoading(true)
    try {
      const res = await api.post('/api/transform/rank', {
        variables: rankVars,
        rank_type: rankType,
        descending: rankDir === 'desc',
        ntiles: rankNTiles,
      })
      const d = res.data
      setRankResult(d)
      outputStore.addEntry('transform', `Rank: ${rankVars.join(', ')}`, d)
      message.success(`Created: ${d.new_columns?.join(', ')}`)
    } catch (e: any) { message.error(e?.response?.data?.detail || 'Rank failed') }
    finally { setLoading(false) }
  }

  // ── Count ──────────────────────────────────────────────────────────────
  const [countVars, setCountVars] = useState<string[]>([])
  const [countValues, setCountValues] = useState('')
  const [countTarget, setCountTarget] = useState('count')
  const [countResult, setCountResult] = useState<any>(null)

  const doCount = async () => {
    if (!countVars.length) { message.warning('Select at least one variable'); return }
    const vals = countValues.split(',').map(v => v.trim()).filter(Boolean)
    if (!vals.length) { message.warning('Enter values to count'); return }
    setLoading(true)
    try {
      const res = await api.post('/api/transform/count', {
        variables: countVars,
        values: vals.map(v => isNaN(Number(v)) ? v : Number(v)),
        target: countTarget,
      })
      setCountResult(res.data)
      outputStore.addEntry('transform', `Count: ${countTarget}`, res.data)
      message.success(`Created column: ${countTarget}`)
    } catch (e: any) { message.error(e?.response?.data?.detail || 'Count failed') }
    finally { setLoading(false) }
  }

  // ── Select If ──────────────────────────────────────────────────────────
  const [selectExpr, setSelectExpr] = useState('age > 50')
  const [selectMode, setSelectMode] = useState<string>('filter')
  const [selectResult, setSelectResult] = useState<any>(null)

  const doSelect = async () => {
    if (!selectExpr.trim()) { message.warning('Enter an expression'); return }
    setLoading(true)
    try {
      const res = await api.post('/api/transform/select-if', {
        expression: selectExpr,
        mode: selectMode,
      })
      setSelectResult(res.data)
      outputStore.addEntry('transform', `Select: ${selectExpr}`, res.data)
      message.success(res.data.mode === 'delete' ? `Deleted ${res.data.deleted} rows` : `Kept ${res.data.kept} rows`)
    } catch (e: any) { message.error(e?.response?.data?.detail || 'Select failed') }
    finally { setLoading(false) }
  }

  // ── Sort ───────────────────────────────────────────────────────────────
  const [sortKeys, setSortKeys] = useState<{ column: string; order: string }[]>([
    { column: '', order: 'asc' },
  ])

  const doSort = async () => {
    const keys = sortKeys.filter(k => k.column)
    if (!keys.length) { message.warning('Add at least one sort key'); return }
    setLoading(true)
    try {
      const res = await api.post('/api/transform/sort', { keys })
      outputStore.addEntry('transform', `Sort by ${keys.map(k => k.column).join(', ')}`, res.data)
      message.success(`Sorted ${res.data.rows} rows`)
      loadColumns()
    } catch (e: any) { message.error(e?.response?.data?.detail || 'Sort failed') }
    finally { setLoading(false) }
  }

  // ── Aggregate ──────────────────────────────────────────────────────────
  const [aggGroup, setAggGroup] = useState<string>('')
  const [aggDefs, setAggDefs] = useState<{ variable: string; function: string }[]>([
    { variable: '', function: 'mean' },
  ])

  const doAggregate = async () => {
    if (!aggGroup) { message.warning('Select a group variable'); return }
    const defs = aggDefs.filter(a => a.variable)
    if (!defs.length) { message.warning('Add at least one aggregate'); return }
    setLoading(true)
    try {
      const res = await api.post('/api/transform/aggregate', {
        group_var: aggGroup,
        aggregates: defs,
      })
      outputStore.addEntry('transform', `Aggregate by ${aggGroup}`, res.data)
      message.success(`Aggregated: ${res.data.rows} groups × ${res.data.cols} cols`)
      loadColumns()
    } catch (e: any) { message.error(e?.response?.data?.detail || 'Aggregate failed') }
    finally { setLoading(false) }
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Data Transformation</Title>
        <Text type="secondary">SPSS-style transform operations — rank, count, select, sort, aggregate</Text>
      </div>

      <Tabs
        items={[
          // ── Rank Tab ────────────────────────────────────────────────
          {
            key: 'rank',
            label: <span><OrderedListOutlined /> Rank Cases</span>,
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div>
                    <Text strong>Variables to rank</Text>
                    <Select mode="multiple" value={rankVars} onChange={setRankVars}
                      options={columns} style={{ width: '100%' }} placeholder="Select numeric variables" />
                  </div>
                  <Space>
                    <div>
                      <Text>Rank type:</Text>
                      <Select value={rankType} onChange={setRankType} style={{ width: 160 }}
                        options={[
                          { label: 'Rank', value: 'rank' },
                          { label: 'Rintile (fractional)', value: 'rintile' },
                          { label: 'Ntile (grouped)', value: 'ntile' },
                          { label: 'Savage score', value: 'savage' },
                          { label: 'Fractional rank', value: 'fractional' },
                        ]} />
                    </div>
                    <div>
                      <Text>Order:</Text>
                      <Radio.Group value={rankDir} onChange={e => setRankDir(e.target.value)}>
                        <Radio.Button value="asc">Ascending</Radio.Button>
                        <Radio.Button value="desc">Descending</Radio.Button>
                      </Radio.Group>
                    </div>
                    {rankType === 'ntile' && (
                      <div>
                        <Text>Ntiles:</Text>
                        <InputNumber min={2} max={100} value={rankNTiles} onChange={v => setRankNTiles(v || 4)} />
                      </div>
                    )}
                  </Space>
                  <Button type="primary" icon={<OrderedListOutlined />} onClick={doRank} loading={loading}>
                    Rank Cases
                  </Button>
                  {rankResult && (
                    <Alert type="success" showIcon message={`Created: ${rankResult.new_columns?.join(', ')}`} />
                  )}
                </Space>
              </Card>
            ),
          },
          // ── Count Tab ────────────────────────────────────────────────
          {
            key: 'count',
            label: <span><NumberOutlined /> Count Occurrences</span>,
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div>
                    <Text strong>Variables to search</Text>
                    <Select mode="multiple" value={countVars} onChange={setCountVars}
                      options={columns} style={{ width: '100%' }} placeholder="Select variables" />
                  </div>
                  <div>
                    <Text strong>Values to count (comma-separated):</Text>
                    <Input value={countValues} onChange={e => setCountValues(e.target.value)}
                      placeholder='e.g. 1, 2, 3 or "Yes", "No"' />
                  </div>
                  <div>
                    <Text>Target column name:</Text>
                    <Input value={countTarget} onChange={e => setCountTarget(e.target.value)}
                      style={{ width: 200 }} placeholder="count" />
                  </div>
                  <Button type="primary" icon={<NumberOutlined />} onClick={doCount} loading={loading}>
                    Count Occurrences
                  </Button>
                  {countResult && (
                    <Alert type="success" showIcon message={`Created column: ${countResult.column}`} />
                  )}
                </Space>
              </Card>
            ),
          },
          // ── Select Tab ───────────────────────────────────────────────
          {
            key: 'select',
            label: <span><FilterOutlined /> Select Cases</span>,
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div>
                    <Text strong>Filter expression (use Python syntax):</Text>
                    <Input.TextArea value={selectExpr} onChange={e => setSelectExpr(e.target.value)}
                      rows={2} placeholder='e.g. age > 50 and sex == "Male"' />
                  </div>
                  <Radio.Group value={selectMode} onChange={e => setSelectMode(e.target.value)}>
                    <Radio value="filter">Filter (keep matching)</Radio>
                    <Radio value="delete">Delete (remove matching)</Radio>
                  </Radio.Group>
                  <Button type="primary" danger={selectMode === 'delete'}
                    icon={<FilterOutlined />} onClick={doSelect} loading={loading}>
                    {selectMode === 'filter' ? 'Apply Filter' : 'Delete Rows'}
                  </Button>
                  {selectResult && (
                    <Alert type={selectResult.mode === 'delete' ? 'error' : 'success'} showIcon
                      message={
                        selectResult.mode === 'delete'
                          ? `Deleted ${selectResult.deleted} rows, ${selectResult.remaining} remaining`
                          : `Kept ${selectResult.kept} rows, ${selectResult.removed} removed`
                      } />
                  )}
                </Space>
              </Card>
            ),
          },
          // ── Sort Tab ─────────────────────────────────────────────────
          {
            key: 'sort',
            label: <span><SortAscendingOutlined /> Sort Cases</span>,
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {sortKeys.map((sk, i) => (
                    <Space key={i}>
                      <Select value={sk.column} onChange={v => {
                        const k = [...sortKeys]; k[i].column = v; setSortKeys(k)
                      }} options={columns} style={{ width: 250 }} placeholder="Select column" />
                      <Radio.Group value={sk.order} onChange={e => {
                        const k = [...sortKeys]; k[i].order = e.target.value; setSortKeys(k)
                      }}>
                        <Radio.Button value="asc">Asc</Radio.Button>
                        <Radio.Button value="desc">Desc</Radio.Button>
                      </Radio.Group>
                      <Button icon={<DeleteOutlined />} size="small" danger
                        onClick={() => setSortKeys(sortKeys.filter((_, j) => j !== i))} />
                    </Space>
                  ))}
                  <Button icon={<PlusOutlined />} onClick={() => setSortKeys([...sortKeys, { column: '', order: 'asc' }])}>
                    Add Sort Key
                  </Button>
                  <Button type="primary" icon={<SortAscendingOutlined />} onClick={doSort} loading={loading}>
                    Sort Cases
                  </Button>
                </Space>
              </Card>
            ),
          },
          // ── Aggregate Tab ────────────────────────────────────────────
          {
            key: 'aggregate',
            label: <span><GroupOutlined /> Aggregate</span>,
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div>
                    <Text strong>Group by variable</Text>
                    <Select value={aggGroup} onChange={setAggGroup} options={columns}
                      style={{ width: '100%' }} placeholder="Select grouping variable" />
                  </div>
                  <Text strong>Aggregates</Text>
                  {aggDefs.map((ad, i) => (
                    <Space key={i}>
                      <Select value={ad.variable} onChange={v => {
                        const a = [...aggDefs]; a[i].variable = v; setAggDefs(a)
                      }} options={columns} style={{ width: 200 }} placeholder="Variable" />
                      <Select value={ad.function} onChange={v => {
                        const a = [...aggDefs]; a[i].function = v; setAggDefs(a)
                      }} style={{ width: 140 }}
                        options={['mean','sum','min','max','std','var','count','first','last','median','nunique']
                          .map(f => ({ label: f, value: f }))} />
                      <Button icon={<DeleteOutlined />} size="small" danger
                        onClick={() => setAggDefs(aggDefs.filter((_, j) => j !== i))} />
                    </Space>
                  ))}
                  <Button icon={<PlusOutlined />} onClick={() => setAggDefs([...aggDefs, { variable: '', function: 'mean' }])}>
                    Add Aggregate
                  </Button>
                  <Button type="primary" icon={<GroupOutlined />} onClick={doAggregate} loading={loading}>
                    Aggregate Data
                  </Button>
                </Space>
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}

export default TransformPage
