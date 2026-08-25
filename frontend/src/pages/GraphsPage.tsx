import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Select, Space, Typography, message, Spin, Row, Col, Tag,
} from 'antd'
import {
  PlayCircleOutlined, FileTextOutlined, DownloadOutlined, SendOutlined,
  BarChartOutlined, DotChartOutlined, ApartmentOutlined,
  ExperimentOutlined, FundOutlined,
} from '@ant-design/icons'
import Plot from '../utils/plotlyWrap'
import ErrorBoundary from '../components/ErrorBoundary'
import EligibilityAlert from '../components/EligibilityAlert'
import ErrorDisplay from '../components/ErrorDisplay'
import { QualityBadge } from '../components/QualityBadge'
import { useEligibilityCheck } from '../hooks/useEligibility'
import { graphApi, datasetApi } from '../api/client'
import outputStore from '../stores/outputStore'
import { seriesToPlotlyChart, capitalize } from '../utils/chartMapping'

const { Text, Title } = Typography

// ── All chart types with eligibility names ──
const GALLERY_ITEMS = [
  { label: 'Histogram', value: 'histogram', icon: FundOutlined, desc: 'Distribution of a continuous variable' },
  { label: 'Boxplot', value: 'boxplot', icon: FundOutlined, desc: 'Distribution summary with quartiles' },
  { label: 'Scatter', value: 'scatter', icon: DotChartOutlined, desc: 'Relationship between two variables' },
  { label: 'Bar Chart', value: 'bar', icon: BarChartOutlined, desc: 'Category frequencies or means' },
  { label: 'ROC Curve', value: 'roc', icon: ExperimentOutlined, desc: 'Diagnostic test performance' },
  { label: 'KM Curve', value: 'km', icon: ApartmentOutlined, desc: 'Survival / time-to-event' },
  { label: 'Violin', value: 'violin', icon: FundOutlined, desc: 'Distribution density across groups' },
  { label: 'Strip Plot', value: 'strip', icon: DotChartOutlined, desc: 'Individual data points across groups' },
  { label: 'ECDF', value: 'ecdf', icon: FundOutlined, desc: 'Cumulative distribution' },
  { label: 'Q-Q Plot', value: 'qq', icon: DotChartOutlined, desc: 'Compare to normal distribution' },
  { label: 'Pareto', value: 'pareto', icon: BarChartOutlined, desc: 'Sorted bar with cumulative line' },
  { label: 'Cleveland Dot', value: 'cleveland_dot', icon: DotChartOutlined, desc: 'Ranked dot comparisons' },
  { label: 'Lollipop', value: 'lollipop', icon: DotChartOutlined, desc: 'Dots with stems' },
  { label: 'Dumbbell', value: 'dumbbell', icon: DotChartOutlined, desc: 'Pre/post change' },
  { label: 'SPLOM', value: 'splom', icon: DotChartOutlined, desc: 'Scatter matrix (3+ vars)' },
  { label: 'Control Chart', value: 'control_chart', icon: FundOutlined, desc: 'Process control limits' },
  { label: 'Run Chart', value: 'run_chart', icon: FundOutlined, desc: 'Time-ordered values' },
  { label: 'Gantt', value: 'gantt', icon: BarChartOutlined, desc: 'Task timeline' },
  { label: 'Calendar Heatmap', value: 'calendar_heatmap', icon: FundOutlined, desc: 'Values by date' },
  { label: 'Parallel Coords', value: 'parallel_coordinates', icon: FundOutlined, desc: 'Multi-dim data' },
  { label: 'Radar', value: 'radar', icon: FundOutlined, desc: 'Multi-attribute profiles' },
  { label: 'Treemap', value: 'treemap', icon: FundOutlined, desc: 'Hierarchical proportions' },
  { label: 'Sankey', value: 'sankey', icon: FundOutlined, desc: 'Flow between categories' },
  { label: 'Waterfall', value: 'waterfall', icon: BarChartOutlined, desc: 'Sequential total' },
  { label: 'Funnel', value: 'funnel', icon: DotChartOutlined, desc: 'Effect size vs precision' },
  { label: 'Bland-Altman', value: 'bland_altman', icon: DotChartOutlined, desc: 'Method comparison' },
  { label: 'Forest Plot', value: 'forest', icon: DotChartOutlined, desc: 'Estimates with CI' },
]



const GraphsPage: React.FC = () => {
  const navigate = useNavigate()
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [columns, setColumns] = useState<string[]>([])
  const [chartType, setChartType] = useState<string>('histogram')
  const [variable, setVariable] = useState<string | undefined>(undefined)
  const [variable2, setVariable2] = useState<string | undefined>(undefined)
  const [groupBy, setGroupBy] = useState<string | undefined>(undefined)
  const [multiVars, setMultiVars] = useState<string[]>([])
  const [timeVar, setTimeVar] = useState<string | undefined>(undefined)
  const [statusVar, setStatusVar] = useState<string | undefined>(undefined)
  const [testVar, setTestVar] = useState<string | undefined>(undefined)
  const [goldVar, setGoldVar] = useState<string | undefined>(undefined)
  const [positiveCode, setPositiveCode] = useState<string>('1')
  const [bins, setBins] = useState<number>(20)
  const [loading, setLoading] = useState(false)
  const [plotData, setPlotData] = useState<any>(null)
  const [chartError, setChartError] = useState<any>(null)
  const plotRef = useRef<any>(null)
  const hasGenerated = useRef(false)

  // ── Auto-refresh chart when variables change ──
  const autoRefreshKey = `${chartType}|${variable}|${variable2}|${groupBy}|${multiVars.join(',')}|${timeVar}|${statusVar}|${testVar}|${goldVar}|${positiveCode}|${bins}`
  useEffect(() => {
    if (hasGenerated.current) {
      const timer = setTimeout(() => generatePlot(), 300)
      return () => clearTimeout(timer)
    }
  }, [autoRefreshKey])

  // ── Eligibility ──
  const eligParams = useMemo(() => {
    const isCont = (v: string) => v && columns.includes(v)
    return {
      analysis: `chart_${chartType}`,
      var_types: { x: variable && isCont(variable) ? 'continuous' : 'nominal', y: variable2 && isCont(variable2) ? 'continuous' : 'nominal' },
    }
  }, [chartType, variable, variable2, columns])
  const eligibility = useEligibilityCheck(eligParams)

  useEffect(() => { loadDatasets() }, [])
  useEffect(() => { if (selectedDataset) loadColumns() }, [selectedDataset])

  const loadDatasets = async () => {
    try {
      const res = await datasetApi.list()
      const ds = res.data || []
      setDatasets(ds)
      if (ds.length > 0 && !selectedDataset) setSelectedDataset(ds[0].id)
    } catch { message.warning('Failed to load datasets') }
  }

  const loadColumns = async () => {
    try { const res = await datasetApi.columns(selectedDataset); setColumns(res.data.columns || res.data || []) } catch { message.warning('Failed to load columns') }
  }

  const colOpts = columns.map(c => ({ label: c, value: c }))

  // ── Chart generation ──
  const generatePlot = async () => {
    if (!selectedDataset) { message.warning('Please select a dataset'); return }

    setLoading(true)
    try {
      let res: any
      switch (chartType) {
        case 'histogram':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.histogram(selectedDataset, variable, bins)
          break
        case 'boxplot':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.boxplot(selectedDataset, variable, groupBy)
          break
        case 'scatter':
          if (!variable || !variable2) { message.warning('Please select X and Y variables'); setLoading(false); return }
          res = await graphApi.scatter(selectedDataset, variable, variable2)
          break
        case 'bar':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.barChart(selectedDataset, variable)
          break
        case 'roc':
          if (!testVar || !goldVar) { message.warning('Please select test and gold standard variables'); setLoading(false); return }
          res = await graphApi.rocCurve(selectedDataset, testVar, goldVar, positiveCode)
          break
        case 'km':
          if (!timeVar || !statusVar) { message.warning('Please select time and status variables'); setLoading(false); return }
          res = await graphApi.kmCurve(selectedDataset, timeVar, statusVar, groupBy)
          break
        case 'violin':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.violin(selectedDataset, variable, groupBy)
          break
        case 'strip':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.strip(selectedDataset, variable, groupBy)
          break
        case 'ecdf':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.ecdf(selectedDataset, variable, groupBy)
          break
        case 'qq':
          if (!variable) { message.warning('Please select a variable'); setLoading(false); return }
          res = await graphApi.qq(selectedDataset, variable)
          break
        case 'pareto':
          if (!variable || !variable2) { message.warning('Select category and value columns'); setLoading(false); return }
          res = await graphApi.pareto(selectedDataset, variable, variable2)
          break
        case 'cleveland_dot':
          if (!variable || !variable2) { message.warning('Select category and value columns'); setLoading(false); return }
          res = await graphApi.clevelandDot(selectedDataset, variable, variable2)
          break
        case 'lollipop':
          if (!variable || !variable2) { message.warning('Select category and value columns'); setLoading(false); return }
          res = await graphApi.lollipop(selectedDataset, variable, variable2)
          break
        case 'dumbbell':
          if (!variable || !variable2 || !groupBy) { message.warning('Select category, pre, and post columns'); setLoading(false); return }
          res = await graphApi.dumbbell(selectedDataset, variable, variable2, groupBy)
          break
        case 'splom':
          if (multiVars.length < 3) { message.warning('Select at least 3 variables'); setLoading(false); return }
          res = await graphApi.splom(selectedDataset, multiVars, groupBy)
          break
        case 'parallel_coordinates':
          if (multiVars.length < 3) { message.warning('Select at least 3 variables'); setLoading(false); return }
          res = await graphApi.parallelCoords(selectedDataset, multiVars, groupBy)
          break
        case 'radar':
          if (!variable || multiVars.length < 3) { message.warning('Select category and at least 3 value columns'); setLoading(false); return }
          res = await graphApi.radar(selectedDataset, variable, multiVars)
          break
        case 'control_chart':
          if (!variable) { message.warning('Select a value column'); setLoading(false); return }
          res = await graphApi.controlChart(selectedDataset, variable, variable2)
          break
        case 'run_chart':
          if (!variable) { message.warning('Select a value column'); setLoading(false); return }
          res = await graphApi.runChart(selectedDataset, variable, variable2)
          break
        case 'gantt':
          if (!variable || !variable2 || !groupBy) { message.warning('Select task, start, and end columns'); setLoading(false); return }
          res = await graphApi.gantt(selectedDataset, variable, variable2, groupBy)
          break
        case 'calendar_heatmap':
          if (!variable || !variable2) { message.warning('Select date and value columns'); setLoading(false); return }
          res = await graphApi.calendarHeatmap(selectedDataset, variable, variable2)
          break
        case 'parallel_coordinates':
          if (!variable) { message.warning('Select 3+ variables from the multi-select'); setLoading(false); return }
          res = await graphApi.parallelCoords(selectedDataset, [variable, variable2].filter(Boolean), groupBy)
          break
        case 'radar':
          if (!variable || !variable2) { message.warning('Select category and 3+ value columns'); setLoading(false); return }
          res = await graphApi.radar(selectedDataset, variable, [variable2].filter(Boolean))
          break
        case 'treemap':
          if (!variable || !variable2) { message.warning('Select category and value columns'); setLoading(false); return }
          res = await graphApi.treemap(selectedDataset, variable, variable2, groupBy)
          break
        case 'sankey':
          if (!variable || !variable2) { message.warning('Select source and target columns'); setLoading(false); return }
          res = await graphApi.sankey(selectedDataset, variable, variable2, groupBy)
          break
        case 'waterfall':
          if (!variable || !variable2) { message.warning('Select category and value columns'); setLoading(false); return }
          res = await graphApi.waterfall(selectedDataset, variable, variable2)
          break
        case 'funnel':
          if (!variable || !variable2) { message.warning('Select effect size and precision columns'); setLoading(false); return }
          res = await graphApi.funnel(selectedDataset, variable, variable2)
          break
        case 'bland_altman':
          if (!variable || !variable2) { message.warning('Select two measurement columns'); setLoading(false); return }
          res = await graphApi.blandAltman(selectedDataset, variable, variable2)
          break
        case 'forest':
          if (!variable || !variable2 || !groupBy) { message.warning('Select label, estimate, CI lower, CI upper'); setLoading(false); return }
          res = await graphApi.forest(selectedDataset, variable, variable2, groupBy, multiVars[0] || '')
          break
      }
      const data = res?.data || res
      if (data?.error) {
        setChartError(data)
        setPlotData(null)
      } else {
        setChartError(null)
        setPlotData(data)
        hasGenerated.current = true
        outputStore.addEntry('graph', chartType + ' chart', data)
        message.success('Chart generated')
      }
    } catch (err: any) {
      const errorData = err?.response?.data || {}
      setChartError(errorData.message || errorData.detail ? errorData : { message: err?.message || 'Chart generation failed', suggestion: 'Check your variable selections and try again.' })
      setPlotData(null)
    } finally { setLoading(false) }
  }

  const downloadPlot = async () => {
    if (plotRef.current) {
      const el = plotRef.current.querySelector('.js-plotly-plot')
      if (el) {
        try {
          const Plotly = await import('plotly.js/dist/plotly')
          Plotly.downloadImage(el, { format: 'png', width: 1200, height: 800, filename: 'devstat-chart' })
        } catch {
          message.info('Right-click the chart and choose "Download as PNG".')
        }
      } else {
        message.info('Generate a chart first before downloading.')
      }
    }
  }

  // ── Send-to-output ──
  const sendToOutput = () => {
    if (!plotData) { message.warning('No chart to send. Generate a chart first.'); return }
    if (typeof outputStore?.addEntry !== 'function') { message.error('Output store not available'); return }
    outputStore.addEntry('graph', `${chartType} chart`, plotData)
    message.success('Chart sent to Output panel')
  }

  // ── SPSS-style variable selectors ──
  const renderVariableSelectors = () => {
    switch (chartType) {
      case 'histogram':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>X-Axis:</Text>
              <Select style={{ width: 250 }} placeholder="Select variable" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Bins:</Text>
              <Select style={{ width: 120 }} value={bins} onChange={setBins} options={[5, 10, 15, 20, 30, 50].map(n => ({ label: String(n), value: n }))} />
            </Space>
          </>
        )
      case 'boxplot':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Y-Axis:</Text>
              <Select style={{ width: 250 }} placeholder="Select variable" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>X-Axis / Group:</Text>
              <Select style={{ width: 250 }} placeholder="Optional grouping" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      case 'scatter':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>X-Axis:</Text>
              <Select style={{ width: 250 }} placeholder="Select X" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Y-Axis:</Text>
              <Select style={{ width: 250 }} placeholder="Select Y" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Group / Color:</Text>
              <Select style={{ width: 250 }} placeholder="Optional grouping" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      case 'bar':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>X-Axis:</Text>
              <Select style={{ width: 250 }} placeholder="Select variable" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Group / Color:</Text>
              <Select style={{ width: 250 }} placeholder="Optional grouping" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      case 'splom':
        case 'parallel_coordinates':
          return (
            <>
              <Space>
                <Text style={{ width: 100 }}>Variables:</Text>
                <Select mode="multiple" style={{ width: 300 }} placeholder="Select 3+ variables" value={multiVars} onChange={setMultiVars} options={colOpts} />
              </Space>
              <Space>
                <Text style={{ width: 100 }}>Color by:</Text>
                <Select style={{ width: 250 }} placeholder="Optional" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
              </Space>
            </>
          )
        case 'radar':
          return (
            <>
              <Space>
                <Text style={{ width: 100 }}>Category:</Text>
                <Select style={{ width: 250 }} placeholder="Select category" value={variable} onChange={setVariable} options={colOpts} />
              </Space>
              <Space>
                <Text style={{ width: 100 }}>Value columns:</Text>
                <Select mode="multiple" style={{ width: 300 }} placeholder="Select 3+ value columns" value={multiVars} onChange={setMultiVars} options={colOpts} />
              </Space>
            </>
          )
      case 'roc':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Test Variable:</Text>
              <Select style={{ width: 250 }} placeholder="Select test variable" value={testVar} onChange={setTestVar} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>State Variable:</Text>
              <Select style={{ width: 250 }} placeholder="Select gold standard" value={goldVar} onChange={setGoldVar} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Value of State:</Text>
              <Select style={{ width: 120 }} value={positiveCode} onChange={setPositiveCode}
                options={[
                  { label: '1', value: '1' },
                  { label: 'Yes', value: 'Yes' },
                  { label: 'Positive', value: 'Positive' },
                  { label: 'True', value: 'True' },
                ]}
              />
            </Space>
          </>
        )
      case 'km':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Time:</Text>
              <Select style={{ width: 250 }} placeholder="Select time" value={timeVar} onChange={setTimeVar} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Status:</Text>
              <Select style={{ width: 250 }} placeholder="Select status" value={statusVar} onChange={setStatusVar} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Group / Color:</Text>
              <Select style={{ width: 250 }} placeholder="Optional factor" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Single numeric + optional group ──
      case 'violin':
      case 'strip':
      case 'ecdf':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Variable:</Text>
              <Select style={{ width: 250 }} placeholder="Select variable" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Group:</Text>
              <Select style={{ width: 250 }} placeholder="Optional" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      case 'qq':
        return (
          <Space>
            <Text style={{ width: 100 }}>Variable:</Text>
            <Select style={{ width: 250 }} placeholder="Select variable" value={variable} onChange={setVariable} options={colOpts} />
          </Space>
        )
      case 'run_chart':
      case 'control_chart':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Value:</Text>
              <Select style={{ width: 250 }} placeholder="Select value column" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Time:</Text>
              <Select style={{ width: 250 }} placeholder="Optional time column" allowClear value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
          </>
        )
      // ── X + Y numeric ──
      case 'hexbin':
      case 'funnel':
      case 'bland_altman':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>X / Effect:</Text>
              <Select style={{ width: 250 }} placeholder="Select X" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Y / Precision:</Text>
              <Select style={{ width: 250 }} placeholder="Select Y" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
          </>
        )
      // ── Category + Value ──
      case 'pareto':
      case 'cleveland_dot':
      case 'lollipop':
      case 'waterfall':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Category:</Text>
              <Select style={{ width: 250 }} placeholder="Select category" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Value:</Text>
              <Select style={{ width: 250 }} placeholder="Select value" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
          </>
        )
      // ── Treemap (optional parent) ──
      case 'treemap':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Category:</Text>
              <Select style={{ width: 250 }} placeholder="Select category" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Value:</Text>
              <Select style={{ width: 250 }} placeholder="Select value" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Parent:</Text>
              <Select style={{ width: 250 }} placeholder="Optional parent" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Dumbbell (pre/post) ──
      case 'dumbbell':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Category:</Text>
              <Select style={{ width: 250 }} placeholder="Select category" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Pre:</Text>
              <Select style={{ width: 250 }} placeholder="Select pre column" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Post:</Text>
              <Select style={{ width: 250 }} placeholder="Select post column" value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Date-based ──
      case 'calendar_heatmap':
      case 'monthly_trend':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Date:</Text>
              <Select style={{ width: 250 }} placeholder="Select date column" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Value:</Text>
              <Select style={{ width: 250 }} placeholder="Select value" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
          </>
        )
      case 'gantt':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Task:</Text>
              <Select style={{ width: 250 }} placeholder="Select task" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Start:</Text>
              <Select style={{ width: 250 }} placeholder="Select start" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>End:</Text>
              <Select style={{ width: 250 }} placeholder="Select end" value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Sankey (source/target) ──
      case 'sankey':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Source:</Text>
              <Select style={{ width: 250 }} placeholder="Select source" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Target:</Text>
              <Select style={{ width: 250 }} placeholder="Select target" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Value:</Text>
              <Select style={{ width: 250 }} placeholder="Optional value" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Bubble (x, y, size) ──
      case 'bubble':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>X:</Text>
              <Select style={{ width: 250 }} placeholder="Select X" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Y:</Text>
              <Select style={{ width: 250 }} placeholder="Select Y" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Size:</Text>
              <Select style={{ width: 250 }} placeholder="Select size" value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Calibration (predicted vs actual) ──
      case 'calibration':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Predicted:</Text>
              <Select style={{ width: 250 }} placeholder="Select predicted" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Actual:</Text>
              <Select style={{ width: 250 }} placeholder="Select actual" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
          </>
        )
      // ── Swimmer (patient timeline) ──
      case 'swimmer':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Patient:</Text>
              <Select style={{ width: 250 }} placeholder="Select patient ID" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Start:</Text>
              <Select style={{ width: 250 }} placeholder="Select start" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>End:</Text>
              <Select style={{ width: 250 }} placeholder="Select end" value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Response:</Text>
              <Select style={{ width: 250 }} placeholder="Optional response" allowClear value={multiVars[0]} onChange={(v) => setMultiVars(v ? [v] : [])} options={colOpts} />
            </Space>
          </>
        )
      // ── AE Heatmap (patient vs event) ──
      case 'ae_heatmap':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Patient:</Text>
              <Select style={{ width: 250 }} placeholder="Select patient" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Event:</Text>
              <Select style={{ width: 250 }} placeholder="Select event" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Grade:</Text>
              <Select style={{ width: 250 }} placeholder="Optional grade" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      // ── Forest (label + est + CI) ──
      case 'forest':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Label:</Text>
              <Select style={{ width: 250 }} placeholder="Select label" value={variable} onChange={setVariable} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Estimate:</Text>
              <Select style={{ width: 250 }} placeholder="Select estimate" value={variable2} onChange={setVariable2} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>CI Lower:</Text>
              <Select style={{ width: 250 }} placeholder="Select CI lower" value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>CI Upper:</Text>
              <Select style={{ width: 250 }} placeholder="Select CI upper" allowClear value={multiVars[0]} onChange={(v) => setMultiVars(v ? [v] : [])} options={colOpts} />
            </Space>
          </>
        )
      // ── Multi-variable charts ──
      case 'pca':
      case 'correlation_heatmap':
      case 'correlation_network':
        return (
          <>
            <Space>
              <Text style={{ width: 100 }}>Variables:</Text>
              <Select mode="multiple" style={{ width: 300 }} placeholder="Select variables" value={multiVars} onChange={setMultiVars} options={colOpts} />
            </Space>
            <Space>
              <Text style={{ width: 100 }}>Group by:</Text>
              <Select style={{ width: 250 }} placeholder="Optional" allowClear value={groupBy} onChange={setGroupBy} options={colOpts} />
            </Space>
          </>
        )
      default:
        return (
          <Space>
            <Text type="secondary">Select a chart type from the gallery above, then choose your variables.</Text>
          </Space>
        )
    }
  }

  // ── Plotly data construction (unchanged logic) ──
  const buildPlotlyData = () => {
    if (!plotData) return null

    const d = plotData.data || plotData.plot || plotData

    // ChartResponse shape: { chart_type, series: [{categories, values, label, ...}] }
    if (d.series && Array.isArray(d.series) && d.series.length > 0) {
      const ct = d.chart_type || chartType
      const { traces, layout } = seriesToPlotlyChart(d.series, ct, {
        title: `${capitalize(ct)} Chart`,
        xTitle: variable || undefined,
        yTitle: 'Value',
      })
      return {
        data: traces,
        layout: {
          template: { layout: { font: { family: 'Inter, sans-serif' }, paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc' } },
          ...layout,
          xaxis: { gridcolor: '#e8ecf1', ...layout.xaxis },
          yaxis: { gridcolor: '#e8ecf1', ...layout.yaxis },
        },
      }
    }

    // Legacy shape: { traces/data: [...], layout: {...} }
    if (d.traces || d.data) {
      const traces = d.traces || d.data
      const layout = d.layout || {}
      return {
        data: traces.map((t: any) => ({ type: t.type || chartType, ...t })),
        layout: {
          template: { layout: { font: { family: 'Inter, sans-serif' }, paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc' } },
          ...layout,
          xaxis: { gridcolor: '#e8ecf1', ...layout.xaxis },
          yaxis: { gridcolor: '#e8ecf1', ...layout.yaxis },
        },
      }
    }

    // Fallback for unrecognized shapes
    const x = d.categories || d.x || d.values || []
    const y = d.values || d.y || []
    if (x.length > 0 || y.length > 0) {
      return {
        data: [{ type: 'bar' as const, x, y, marker: { color: '#005eb8' }, name: variable || '' }],
        layout: {
          title: (d.chart_type || chartType || 'Chart').charAt(0).toUpperCase() + (d.chart_type || chartType || 'Chart').slice(1),
          xaxis: { title: d.column || variable || '', gridcolor: '#e8ecf1' },
          yaxis: { title: 'Value', gridcolor: '#e8ecf1' },
          font: { family: 'Inter, sans-serif' },
          paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
          margin: { l: 60, r: 30, t: 50, b: 60 },
        },
      }
    }

    return null
  }

  const plotlyConfig = {
    displayModeBar: true, displaylogo: false, responsive: true,
    modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
    toImageButtonOptions: { format: 'png', filename: 'devstat-chart', width: 1200, height: 800 },
  }

  const plotObj = buildPlotlyData()
  const plotlyLayout = plotObj?.layout || {}
  const plotlyData = plotObj?.data || []

  // ── Derived active gallery info ──
  const activeGalleryItem = GALLERY_ITEMS.find(i => i.value === chartType)
  const ActiveIcon = activeGalleryItem?.icon

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16, color: '#1a1a2e' }}>Graphs & Charts</Title>

      {/* ── SPSS-style Chart Type Gallery (3×2 grid) ── */}
      <Card
        title={
          <Space>
            <span>Chart Builder Gallery</span>
            {activeGalleryItem && (
              <Tag icon={ActiveIcon ? <ActiveIcon /> : undefined} color="processing">
                {activeGalleryItem.label}
              </Tag>
            )}
          </Space>
        }
        style={{ marginBottom: 16 }}
        bodyStyle={{ padding: '16px 16px 8px 16px' }}
      >
        <Row gutter={[12, 12]}>
          {GALLERY_ITEMS.map(item => {
            const Icon = item.icon
            const isActive = chartType === item.value
            return (
              <Col span={8} key={item.value}>
                <Card
                  hoverable
                  size="small"
                  onClick={() => setChartType(item.value)}
                  style={{
                    cursor: 'pointer',
                    textAlign: 'center',
                    borderRadius: 8,
                    border: isActive ? '2px solid #005eb8' : '1px solid #e8ecf1',
                    background: isActive ? '#f0f7ff' : '#fff',
                    transition: 'all 0.2s',
                  }}
                  bodyStyle={{ padding: '14px 8px' }}
                >
                  <Icon
                    style={{
                      fontSize: 28,
                      color: isActive ? '#005eb8' : '#8892b0',
                      display: 'block',
                      marginBottom: 6,
                    }}
                  />
                  <Text strong style={{ fontSize: 13, color: isActive ? '#005eb8' : '#1a1a2e' }}>
                    {item.label}
                  </Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {item.desc}
                  </Text>
                </Card>
              </Col>
            )
          })}
        </Row>
      </Card>

      {/* ── Configuration panel ── */}
      <Card title="Chart Configuration" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space>
            <Text style={{ width: 100 }}>Dataset:</Text>
            <Select
              style={{ width: 300 }}
              placeholder="Select dataset"
              value={selectedDataset || undefined}
              onChange={setSelectedDataset}
              options={datasets.map((d: any) => ({ label: d.filename || d.name || d.id, value: d.id }))}
            />
          </Space>
          {renderVariableSelectors()}
        </Space>
      </Card>

      {/* ── Eligibility warning ── */}
      <EligibilityAlert result={eligibility} />

      <ErrorDisplay error={chartError} />

      {/* ── Action buttons ── */}
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={generatePlot} loading={loading}>
          Generate Chart
        </Button>
        {plotData && (
          <>
            <Button icon={<DownloadOutlined />} onClick={downloadPlot}>
              Download PNG
            </Button>
            <Button icon={<SendOutlined />} onClick={sendToOutput}>
              Send to Output
            </Button>
          </>
        )}
      </Space>

      {/* ── Loading indicator ── */}
      {loading && (
        <Card>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
            <Text style={{ marginLeft: 12 }}>Generating chart...</Text>
          </div>
        </Card>
      )}

      {/* ── Plotly chart output ── */}
      {plotData && !loading && (
        <ErrorBoundary>
          <Card ref={plotRef} bodyStyle={{ padding: 12 }} style={{ maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }} extra={<Button size="small" icon={<FileTextOutlined />} onClick={() => { navigate('/output') }}>View Full Results</Button>}>
            {plotlyData.length > 0 && typeof Plot === 'function' ? (
              <Plot
                data={plotlyData}
                layout={{ ...plotlyLayout, autosize: true, height: 500 }}
                config={plotlyConfig}
                useResizeHandler
                style={{ width: '100%' }}
              />
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>
                <Text type="secondary">No chart data to display. Select a dataset and chart type, then click Generate Chart.</Text>
              </div>
            )}
          </Card>
        </ErrorBoundary>
      )}
    </div>
  )
}

export default GraphsPage
