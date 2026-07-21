import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Card, Button, Space, Typography, message, Tree, Tag, Table, Empty, Tabs, Collapse, Checkbox, Tooltip,
} from 'antd'
import {
  ClearOutlined, DeleteOutlined, FileTextOutlined, DownloadOutlined,
  BarChartOutlined, FundOutlined, ApartmentOutlined,
  ExperimentOutlined, NodeIndexOutlined, TableOutlined, CopyOutlined, SelectOutlined,
} from '@ant-design/icons'
import outputStore from '../stores/outputStore'
import type { OutputEntry, OutputNode } from '../stores/outputStore'
import Plot from '../utils/plotlyWrap'
import BlockedAnalysisPanel from '../components/BlockedAnalysisPanel'
import { normalizeResult, safeKeys } from '../utils/responseNormalizer'
import type { NormalizedResult } from '../utils/responseNormalizer'

const { Text, Title } = Typography

const TYPE_COLORS: Record<string, string> = {
  data: 'blue', descriptive: 'purple', compare: 'orange', nonparametric: 'orange',
  regression: 'green', survival: 'red', diagnostic: 'cyan', correlation: 'geekblue',
  factor: 'magenta', graph: 'magenta',
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  data: <TableOutlined />, descriptive: <FundOutlined />, compare: <ExperimentOutlined />,
  nonparametric: <ExperimentOutlined />, regression: <NodeIndexOutlined />,
  survival: <ApartmentOutlined />, diagnostic: <ExperimentOutlined />,
  correlation: <NodeIndexOutlined />, factor: <ExperimentOutlined />, graph: <BarChartOutlined />,
}

function columnsFromData(data: any[]): any[] {
  if (!data.length) return []
  const keys = safeKeys(data[0]).filter(k => k !== '_key')
  return keys.map(key => ({
    title: key.replace(/_/g, ' ').replace(/^(.)/, c => c.toUpperCase()),
    dataIndex: key, key,
    render: (v: any) => v === null || v === undefined ? <Text type="secondary">.</Text>
      : typeof v === 'number' ? v.toFixed(4) : typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v),
  }))
}

function renderResultContent(entry: OutputEntry): React.ReactNode {
  const normalized = normalizeResult(entry.type, entry.result)
  const { tables, charts, narrative, warnings, _blocked } = normalized
  if (_blocked) return <BlockedAnalysisPanel result={_blocked} />
  const tabs: any[] = []
  if (tables.length > 0) {
    tabs.push({ key: 'table', label: `Table (${tables.length})`, children: <Table dataSource={tables} columns={columnsFromData(tables)} rowKey="_key" pagination={false} size="small" bordered scroll={{ x: 'max-content' }} /> })
  }
  if (charts.length > 0) {
    tabs.push({ key: 'chart', label: `Chart (${charts.length})`, children: <div style={{ padding: 8 }}>{charts.map((c: any, i: number) => <ChartCard key={i} chart={c} />)}</div> })
  }
  if (narrative) {
    tabs.push({ key: 'narrative', label: 'Summary', children: <div style={{ padding: 16, background: '#f0f7ff', borderRadius: 6, border: '1px solid #bae0ff', fontSize: 13, color: '#334155', lineHeight: 1.6 }}>{narrative}</div> })
  }
  if (warnings.length > 0 && tabs.length === 0) {
    tabs.push({ key: 'warnings', label: 'Warnings', children: <div style={{ padding: 16 }}>{warnings.map((w, i) => <div key={i} style={{ marginBottom: 8, padding: 8, background: '#fff3e0', borderRadius: 4, border: '1px solid #ffe0b2' }}><Text type="warning">{w}</Text></div>)}</div> })
  }
  if (tabs.length === 0) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Empty description="Result could not be rendered" /><Collapse ghost size="small" style={{ marginTop: 16, maxWidth: 480, margin: '16px auto 0' }}><Collapse.Panel key="raw" header="Raw Data"><pre style={{ fontSize: 11, maxHeight: 300, overflow: 'auto', background: '#f8fafc', padding: 12, borderRadius: 4, border: '1px solid #e2e8f0', margin: 0 }}>{JSON.stringify(entry.result, null, 2)}</pre></Collapse.Panel></Collapse></div>
  }
  return <Tabs items={tabs} defaultActiveKey={tabs[0].key} />
}

function seriesToPlotlyTraces(series: any[], chartType: string): any[] {
  return series.map((s: any) => {
    const trace: any = { type: 'scatter', mode: 'lines', name: s.group || s.label || '' }
    if (s.x && s.y) {
      trace.x = s.x
      trace.y = s.y
    } else if (s.values) {
      trace.y = s.values
      trace.type = chartType === 'boxplot' ? 'box' : 'bar'
      trace.mode = 'markers'
    }
    if (s.ci_lower && s.ci_upper && s.x) {
      trace.error_y = { type: 'data', symmetric: false, array: s.ci_upper.map((u: number, i: number) => u - s.y[i]), arrayminus: s.ci_lower.map((l: number, i: number) => s.y[i] - l) }
    }
    return trace
  })
}

function ChartCard({ chart }: { chart: any }) {
  const chartType = chart.type ?? chart.chart_type ?? 'bar'
  const data = chart?.data || chart
  // Support two shapes: {data: {series, layout}} or {traces, layout} (direct from batch chart functions)
  const series = data.series
  const directTraces = data.traces
  const traces = directTraces || (series ? seriesToPlotlyTraces(Array.isArray(series) ? series : [series], chartType) : [])
  const layout = data.layout || { title: chart.title || chartType, xaxis: { title: '' }, yaxis: { title: '' } }

  if (traces.length === 0) {
    return (
      <Card size="small" title={chart.title ?? chartType} style={{ marginBottom: 12 }}>
        <div style={{ background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0', padding: 12, minHeight: 60, textAlign: 'center' }}>
          <Text type="secondary">{chartType} chart</Text>
        </div>
      </Card>
    )
  }

  return (
    <Card size="small" title={chart.title ?? chartType} style={{ marginBottom: 12, maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}
      extra={<Button type="text" icon={<DownloadOutlined />} size="small" onClick={() => message.info('Chart download via backend coming soon')} />}>
      <Plot data={traces} layout={layout} config={{ responsive: true }} style={{ width: '100%', height: 350 }} />
    </Card>
  )
}

function EntryCard({ entry, selected, onToggleSelect }: { entry: OutputEntry; selected: boolean; onToggleSelect: (id: string) => void }) {
  return (
    <Card size="small" style={{ marginBottom: 8, borderLeft: `3px solid ${TYPE_COLORS[entry.category] || '#d9d9d9'}` }}
      title={<Space size={4}><Tag color={TYPE_COLORS[entry.category]} style={{ fontSize: 9, lineHeight: '16px', padding: '0 4px', margin: 0 }}>{entry.type}</Tag><Text style={{ fontSize: 13 }}>{entry.title}</Text><Text type="secondary" style={{ fontSize: 11 }}>{entry.timestamp}</Text></Space>}
      extra={<Checkbox checked={selected} onChange={() => onToggleSelect(entry.id)} />}>
      {renderResultContent(entry)}
    </Card>
  )
}

const OutputPage: React.FC = () => {
  const [treeNodes, setTreeNodes] = useState<OutputNode[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])
  const [compareMode, setCompareMode] = useState(false)
  const [, forceUpdate] = useState(0)

  useEffect(() => {
    refresh()
    const highlight = outputStore.consumeHighlight()
    if (highlight) setSelectedId(highlight)
    const unsub = outputStore.subscribe(() => { refresh(); forceUpdate(n => n + 1) })
    return unsub
  }, [])

  const refresh = () => {
    setTreeNodes(outputStore.buildTreeNodes())
    setExpandedKeys(outputStore.buildTreeNodes().map(n => n.key))
  }

  const selectedEntry = selectedId ? outputStore.getEntry(selectedId) : null
  const selectedIds = outputStore.getSelectedIds()
  const selectedEntries = outputStore.getSelectedEntries()

  const handleToggleSelect = useCallback((id: string) => {
    outputStore.toggleSelect(id)
    forceUpdate(n => n + 1)
  }, [])

  const handleCompare = useCallback(() => {
    if (selectedIds.length < 2) { message.warning('Select at least 2 results to compare'); return }
    outputStore.setCompareMode(true)
    setCompareMode(true)
  }, [selectedIds])

  const handleExportPDF = useCallback(() => {
    if (selectedIds.length === 0) { message.warning('Select results to export'); return }
    message.info('PDF export via backend coming soon — using browser print for now')
    window.print()
  }, [selectedIds])

  const handlePrintResults = useCallback(() => {
    window.print()
  }, [])

  const treeData = useMemo(() => {
    const convertNodes = (nodes: OutputNode[]): any[] =>
      nodes.map(node => ({
        key: node.key,
        title: node.type === 'category'
          ? <span style={{ fontWeight: 600, fontSize: 12 }}>{node.title} ({node.children?.length || 0})</span>
          : <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Tag color={TYPE_COLORS[node.entry?.category || 'descriptive']} style={{ fontSize: 9, lineHeight: '16px', padding: '0 4px', margin: 0 }}>{node.entry?.type}</Tag>
              <Checkbox size="small" checked={outputStore.isSelected(node.key)} onChange={() => handleToggleSelect(node.key)} />
              <span style={{ fontSize: 12 }}>{node.title}</span>
            </span>,
        children: node.children ? convertNodes(node.children) : undefined,
      }))
    return convertNodes(treeNodes)
  }, [treeNodes, handleToggleSelect])

  const renderDetail = () => {
    if (compareMode && selectedEntries.length >= 2) {
      return (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Button onClick={() => { outputStore.setCompareMode(false); setCompareMode(false) }}>Exit Comparison</Button>
            <Button icon={<DownloadOutlined />} onClick={handlePrintResults}>Print Comparison</Button>
          </Space>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {selectedEntries.map(entry => (
              <div key={entry.id} style={{ flex: '1 1 45%', minWidth: 350 }}>
                <EntryCard entry={entry} selected={false} onToggleSelect={() => {}} />
              </div>
            ))}
          </div>
        </div>
      )
    }

    if (!selectedEntry) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400, flexDirection: 'column', gap: 12 }}>
          <FileTextOutlined style={{ fontSize: 48, color: '#cbd5e0' }} />
          <Text type="secondary" style={{ fontSize: 16 }}>Select an analysis from the outline</Text>
          {selectedIds.length >= 2 && (
            <Button type="primary" icon={<CopyOutlined />} onClick={handleCompare}>Compare Selected ({selectedIds.length})</Button>
          )}
        </div>
      )
    }

    return (
      <div>
        <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
          <Space>
            <Tag color={TYPE_COLORS[selectedEntry.category] || 'default'} style={{ fontSize: 11 }}>
              {TYPE_ICONS[selectedEntry.category]} {selectedEntry.type.toUpperCase()}
            </Tag>
            <Text strong style={{ fontSize: 14 }}>{selectedEntry.title}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{selectedEntry.timestamp}</Text>
          </Space>
        </div>
        {renderResultContent(selectedEntry)}
      </div>
    )
  }

  const hasEntries = treeNodes.some(n => (n.children?.length || 0) > 0)

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 240px)' }}>
        <Card title={<Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <span>History</span>
          {hasEntries && <Button type="text" danger icon={<ClearOutlined />} size="small" onClick={() => { outputStore.clearAll(); setSelectedId(null) }}>Clear</Button>}
        </Space>} style={{ width: 300, minWidth: 300, display: 'flex', flexDirection: 'column' }}
          styles={{ body: { flex: 1, overflow: 'auto', padding: '8px 0' } }}>
          {!hasEntries ? <div style={{ textAlign: 'center', padding: 40 }}><Empty description="No results yet" /></div>
            : <Tree showLine defaultExpandAll expandedKeys={expandedKeys} onExpand={setExpandedKeys}
              onSelect={(keys) => { const k = keys[0] as string; if (k && !k.startsWith('cat-')) setSelectedId(k) }}
              selectedKeys={selectedId ? [selectedId] : []}
              treeData={treeData} />}
        </Card>
        <Card title={compareMode ? 'Comparison View' : (selectedEntry?.title || 'Results Viewer')}
          extra={<Space>
            {selectedIds.length >= 2 && !compareMode && <Button icon={<CopyOutlined />} onClick={handleCompare}>Compare ({selectedIds.length})</Button>}
            {hasEntries && <><Button icon={<DownloadOutlined />} onClick={handleExportPDF}>Export PDF</Button><Button icon={<SelectOutlined />} onClick={() => outputStore.selectAll()}>Select All</Button></>}
          </Space>}
          style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
          styles={{ body: { flex: 1, overflow: 'auto' } }}>
          {renderDetail()}
        </Card>
      </div>
    </div>
  )
}

export default OutputPage
