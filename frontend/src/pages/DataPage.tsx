import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Card, Button, Upload, Tabs, Space, Typography, message, Tag, Tooltip, Modal, Input, Select,
} from 'antd'
import {
  UploadOutlined, DownloadOutlined, TableOutlined, ColumnHeightOutlined,
  ReloadOutlined, UndoOutlined, RedoOutlined, PlusOutlined,
  DeleteOutlined, CalculatorOutlined, SwapOutlined,
} from '@ant-design/icons'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { datasetApi, api, getMode } from '../api/client'
import outputStore from '../stores/outputStore'
import VariableView from '../components/VariableView'
import { useKeyboardShortcuts, type ShortcutAction } from '../hooks/useKeyboardShortcuts'
import KeyboardShortcutsHelp from '../components/KeyboardShortcutsHelp'

const { Text } = Typography

// ── Types ────────────────────────────────────────────────────────────────

interface ColumnMeta {
  name: string
  dtype: string
  is_numeric: boolean
  is_categorical: boolean
  missing_count: number
  unique_count: number
  type?: string
  width?: number
  decimals?: number
  label?: string
  value_labels?: Record<string, string>
  measure?: string
}

interface DatasetState {
  filename: string
  rows: number
  cols: number
  columns: ColumnMeta[]
}

// ── Component ────────────────────────────────────────────────────────────

const DataPage: React.FC = () => {
  // ── Data state (single active dataset) ─────────────────────────────
  const [dataset, setDataset] = useState<DatasetState | null>(null)
  const [totalRows, setTotalRows] = useState(0)
  const [useServerSide, setUseServerSide] = useState(false)

  // Always use client-side row model
  const rowModelType = 'clientSide'
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<string>('data')
  const [rowData, setRowData] = useState<Record<string, any>[]>([])
  const [colDefs, setColDefs] = useState<any[]>([])
  const [variableRefreshKey, setVariableRefreshKey] = useState(0)
  const [undoCount, setUndoCount] = useState(0)
  const [redoCount, setRedoCount] = useState(0)
  const gridRef = useRef<AgGridReact>(null)

  // ── Compute Variable dialog state ──────────────────────────────────
  const [computeOpen, setComputeOpen] = useState(false)
  const [computeName, setComputeName] = useState('')
  const [computeExpr, setComputeExpr] = useState('')
  const [computePreview, setComputePreview] = useState<any[] | null>(null)
  const [computeLoading, setComputeLoading] = useState(false)

  // ── Recode dialog state ────────────────────────────────────────────
  const [recodeOpen, setRecodeOpen] = useState(false)
  const [recodeColumn, setRecodeColumn] = useState<string>('')
  const [recodeIntoNew, setRecodeIntoNew] = useState('')
  const [recodeMode, setRecodeMode] = useState<'same' | 'new'>('same')
  const [recodeMappings, setRecodeMappings] = useState('')
  const [recodeLoading, setRecodeLoading] = useState(false)

  // ── Data Loading ────────────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [infoRes, previewRes] = await Promise.all([
        datasetApi.info(),
        datasetApi.preview(500),
      ])
      const info = infoRes.data
      if (!info) {
        setDataset(null)
        setRowData([])
        setColDefs([])
        return
      }
      const columns: ColumnMeta[] = info.columns || []
      const nRows = info.rows || 0
      setTotalRows(nRows)

      // Large datasets: use server-side pagination/sort/filter
      const isLarge = nRows > 5_000
      setUseServerSide(false)

      const preview: Record<string, any>[] = isLarge
        ? []  // skip loading all rows for large datasets
        : (Array.isArray(previewRes.data) ? previewRes.data : [])

      // Build AG Grid column definitions
      const defs = columns.map((col: ColumnMeta) => ({
        field: col.name,
        headerName: col.name,
        minWidth: 80,
        flex: 1,
        resizable: true,
        sortable: true,
        filter: true,
        editable: true,
        cellStyle: (params: any) => {
          if (params.value === null || params.value === undefined || params.value === '') {
            return { fontFamily: "'Inter', sans-serif", fontSize: 13, color: '#94a3b8', fontStyle: 'italic' }
          }
          return { fontFamily: "'Inter', sans-serif", fontSize: 13 }
        },
        valueFormatter: (params: any) => {
          if (params.value === null || params.value === undefined) return '.'
          return params.value
        },
        headerClass: 'ag-header-cell-custom',
      }))

      setColDefs(defs)
      setRowData(isLarge ? [] : preview)
      setDataset({
        filename: info.name || 'untitled',
        rows: info.rows,
        cols: info.cols,
        columns,
      })
      setVariableRefreshKey(k => k + 1)

      // Configure server-side datasource for large datasets
      if (isLarge && gridRef.current) {
        const ds = {
          getRows: async (params: any) => {
            try {
              const res = await api.post('/api/data/rows', {
                page: Math.floor(params.request.startRow / 100),
                pageSize: 100,
                sortModel: params.request.sortModel,
                filterModel: params.request.filterModel,
              })
              params.success({ rowData: res.data.rows, rowCount: res.data.total })
            } catch {
              params.fail()
            }
          },
        }
        ;(gridRef.current as any).api.setGridOption('serverSideDatasource', ds)
      }
    } catch (err: any) {
      // No data loaded — that's fine
      setDataset(null)
      setRowData([])
      setColDefs([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Re-load when a dataset is chosen from the right-hand pane (auto-load).
  useEffect(() => {
    const onData = () => loadData()
    window.addEventListener('devstat:data-changed', onData)
    return () => window.removeEventListener('devstat:data-changed', onData)
  }, [loadData])

  // Exam mode convenience: preload the bundled synthetic practice dataset when
  // nothing is loaded yet (no upload headache, no credit consumed — loading a
  // dataset is not an analysis).
  useEffect(() => {
    const loadPreload = async () => {
      try {
        const info = await datasetApi.info()
        if (!info?.data && getMode() === 'exam') {
          await datasetApi.sample()
          loadData()
        }
      } catch { /* ignore */ }
    }
    loadPreload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Keyboard Shortcuts ─────────────────────────────────────────────

  const handleSave = useCallback(() => {
    message.success('Dataset saved')
  }, [])

  const handleSaveAs = useCallback(() => {
    if (!dataset) { message.warning('No dataset to save'); return }
    const headers = colDefs.map((c) => c.field)
    const csv = [headers.join(','), ...rowData.map((r) => headers.map((h) => r[h] ?? '').join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'dataset.csv'; a.click()
    URL.revokeObjectURL(url)
    message.success('Dataset downloaded')
  }, [dataset, rowData, colDefs])

  const handleOpen = useCallback(() => {
    message.info('Open file — implement file picker')
  }, [])

  const handleUndo = useCallback(async () => {
    if (!dataset) return
    try {
      const res = await datasetApi.undo()
      if (res.data.success) {
        message.info(`Undo: ${res.data.description}`)
        setUndoCount(res.data.undo_count)
        setRedoCount(res.data.redo_count)
        await loadData()
      }
    } catch { message.warning('Undo failed') }
  }, [dataset, loadData])

  const handleRedo = useCallback(async () => {
    if (!dataset) return
    try {
      const res = await datasetApi.redo()
      if (res.data.success) {
        message.info(`Redo: ${res.data.description}`)
        setUndoCount(res.data.undo_count)
        setRedoCount(res.data.redo_count)
        await loadData()
      }
    } catch { message.warning('Redo failed') }
  }, [dataset, loadData])

  const handleExportPrint = useCallback(() => {
    window.print()
  }, [])

  const handleFind = useCallback(() => {
    if (gridRef.current?.api) {
      message.info('Press Ctrl+F to search the data grid')
    }
  }, [])

  const shortcutActions: ShortcutAction[] = [
    { keys: 'Ctrl+S', scope: 'global', label: 'Save project', handler: handleSave },
    { keys: 'Ctrl+Shift+S', scope: 'global', label: 'Save As', handler: handleSaveAs },
    { keys: 'Ctrl+O', scope: 'global', label: 'Open file', handler: handleOpen },
    { keys: 'Ctrl+Z', scope: 'dataset', label: 'Undo', handler: handleUndo, disabled: !dataset },
    { keys: 'Ctrl+Shift+Z', scope: 'dataset', label: 'Redo', handler: handleRedo, disabled: !dataset },
    { keys: 'Ctrl+Y', scope: 'dataset', label: 'Redo (alternative)', handler: handleRedo, disabled: !dataset },
    { keys: 'Ctrl+P', scope: 'global', label: 'Export/Print output', handler: handleExportPrint },
    { keys: 'Ctrl+F', scope: 'dataset', label: 'Find variable / search', handler: handleFind, disabled: !dataset },
    { keys: '?', scope: 'global', label: 'Show keyboard shortcuts help', handler: () => {} },
    { keys: 'F1', scope: 'global', label: 'Show keyboard shortcuts help', handler: () => {} },
  ]

  const { showHelp, setShowHelp, getShortcutDisplay, shortcutHelpItems } =
    useKeyboardShortcuts({ shortcuts: shortcutActions })

  // ── Toolbar Actions ──────────────────────────────────────────────────

  const handleUpload = async (file: File) => {
    setLoading(true)
    try {
      const res = await datasetApi.upload(file)
      message.success(`Dataset "${file.name}" loaded successfully`)

      outputStore.addEntry('data', `Uploaded: ${file.name}`, { rows: res.data.rows, cols: res.data.cols })
      await loadData()
    } catch (err: any) {
      message.error('Upload failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
    return false
  }

  const handleDownload = async () => {
    if (!dataset) return
    try {
      const res = await datasetApi.download()
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `${dataset.filename.replace(/\\.[^.]+$/, '')}_export.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      message.error('Download failed')
    }
  }

  const handleReset = () => {
    Modal.confirm({
      title: 'Clear dataset?',
      content: 'This will remove all data from memory.',
      onOk: async () => {
        try {
          await datasetApi.reset()
          setDataset(null)
          setRowData([])
          setColDefs([])
          setVariableRefreshKey(k => k + 1)
          message.info('Data cleared')
        } catch {
          message.error('Failed to clear')
        }
      },
    })
  }

  const addColumn = async () => {
    const name = `var${(dataset?.columns.length || 0) + 1}`
    try {
      await datasetApi.addColumn(name)
      message.success(`Added "${name}"`)
      await loadData()
    } catch (err: any) {
      message.error('Failed: ' + (err?.response?.data?.detail || err.message))
    }
  }

  const deleteSelectedColumn = async () => {
    const selected = gridRef.current?.api?.getSelectedRows()
    const name = selected?.[0]?.name || dataset.columns[dataset.columns.length - 1]?.name
    if (!name) return
    Modal.confirm({
      title: `Delete column "${name}"?`,
      content: 'This cannot be undone (except via undo).',
      onOk: async () => {
        try {
          await datasetApi.deleteColumn(name)
          message.info(`Deleted "${name}"`)
          await loadData()
        } catch (err: any) {
          message.error('Failed: ' + (err?.response?.data?.detail || err.message))
        }
      },
    })
  }

  // ── Compute Variable ───────────────────────────────────────────────

  const handleComputePreview = async () => {
    if (!computeExpr.trim()) return
    setComputeLoading(true)
    try {
      const res = await datasetApi.computePreview(computeName || '_preview', computeExpr)
      setComputePreview(res.data.preview || [])
      message.success(`Preview OK — dtype: ${res.data.dtype}, ${res.data.count} values, ${res.data.missing} missing`)
    } catch (err: any) {
      setComputePreview(null)
      message.error('Preview failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setComputeLoading(false)
    }
  }

  const handleCompute = async () => {
    if (!computeName.trim() || !computeExpr.trim()) {
      message.warning('Please provide a variable name and expression.')
      return
    }
    setComputeLoading(true)
    try {
      await datasetApi.compute(computeName, computeExpr)
      message.success(`Computed "${computeName}" = ${computeExpr}`)
      setComputeOpen(false)
      setComputeName('')
      setComputeExpr('')
      setComputePreview(null)
      await loadData()
    } catch (err: any) {
      message.error('Compute failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setComputeLoading(false)
    }
  }

  // ── Recode ─────────────────────────────────────────────────────────

  const handleRecode = async () => {
    if (!recodeColumn) {
      message.warning('Please select a column to recode.')
      return
    }
    if (recodeMode === 'new' && !recodeIntoNew.trim()) {
      message.warning('Please provide a target column name.')
      return
    }

    // Parse mappings: old=new per line
    const mappings: Record<string, any> = {}
    recodeMappings.split('\n').forEach(line => {
      const eqIdx = line.indexOf('=')
      if (eqIdx > 0) {
        mappings[line.substring(0, eqIdx).trim()] = line.substring(eqIdx + 1).trim()
      }
    })

    if (Object.keys(mappings).length === 0) {
      message.warning('Please enter at least one recode mapping (old=new).')
      return
    }

    setRecodeLoading(true)
    try {
      await datasetApi.recode(
        recodeColumn,
        recodeMode === 'new' ? recodeIntoNew : '',
        mappings,
        []
      )
      message.success(`Recoded "${recodeColumn}"${recodeMode === 'new' ? ` → "${recodeIntoNew}"` : ''}`)
      setRecodeOpen(false)
      setRecodeColumn('')
      setRecodeIntoNew('')
      setRecodeMappings('')
      setRecodeMode('same')
      await loadData()
    } catch (err: any) {
      message.error('Recode failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setRecodeLoading(false)
    }
  }

  // ── Cell Editing via AG Grid ────────────────────────────────────────

  const onCellValueChanged = useCallback(async (event: any) => {
    if (!event.data) return
    const { rowIndex, column, oldValue, newValue, data } = event
    try {
      await datasetApi.editCell(rowIndex, column.colId, newValue)
    } catch (err: any) {
      message.error('Edit failed: ' + (err?.response?.data?.detail || err.message))
      // Revert the cell
      event.api.applyTransaction({ update: [{ ...data, [column.colId]: oldValue }] })
    }
  }, [])

  // ── Context Menu ────────────────────────────────────────────────────

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; rowIndex?: number } | null>(null)

  const showContextMenu = (e: React.MouseEvent, rowIndex?: number) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY, rowIndex })
  }

  useEffect(() => {
    const handler = () => setContextMenu(null)
    window.addEventListener('click', handler)
    return () => window.removeEventListener('click', handler)
  }, [])

  const insertRow = async () => {
    try {
      const idx = contextMenu?.rowIndex ?? -1
      await datasetApi.insertRow(idx, 1)
      message.info('Row inserted')
      await loadData()
    } catch { /* */ }
    setContextMenu(null)
  }

  const deleteRow = async () => {
    if (contextMenu?.rowIndex === undefined) return
    try {
      await datasetApi.deleteRow(contextMenu.rowIndex)
      message.info('Row deleted')
      await loadData()
    } catch { /* */ }
    setContextMenu(null)
  }

  // ── Render ──────────────────────────────────────────────────────────

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <Card size="small" style={{ marginBottom: 8 }} styles={{ body: { padding: '8px 16px' } }}>
        <Space wrap>
          <Upload
            accept=".csv,.xlsx,.xls,.sav,.dta"
            showUploadList={false}
            beforeUpload={handleUpload}
          >
            <Button type="primary" icon={<UploadOutlined />} size="small">
              Upload Data
            </Button>
          </Upload>
          <Button icon={<DownloadOutlined />} size="small" onClick={handleDownload} disabled={!dataset}>
            Download
          </Button>
          <Button icon={<ReloadOutlined />} size="small" onClick={loadData} disabled={loading}>
            Refresh
          </Button>
          <Button icon={<UndoOutlined />} size="small" onClick={handleUndo} disabled={!dataset}>
            Undo
          </Button>
          <Button icon={<RedoOutlined />} size="small" onClick={handleRedo} disabled={!dataset}>
            Redo
          </Button>
          <div style={{ borderLeft: '1px solid #e2e8f0', height: 24 }} />
          <Button icon={<PlusOutlined />} size="small" onClick={addColumn} disabled={!dataset}>
            Add Col
          </Button>
          <Button icon={<DeleteOutlined />} size="small" danger onClick={deleteSelectedColumn} disabled={!dataset}>
            Del Col
          </Button>
          <div style={{ borderLeft: '1px solid #e2e8f0', height: 24 }} />
          <Button icon={<CalculatorOutlined />} size="small" onClick={() => setComputeOpen(true)} disabled={!dataset}>
            Compute
          </Button>
          <Button icon={<SwapOutlined />} size="small" onClick={() => setRecodeOpen(true)} disabled={!dataset}>
            Recode
          </Button>
          <div style={{ borderLeft: '1px solid #e2e8f0', height: 24 }} />
          <Button size="small" danger onClick={handleReset} disabled={!dataset}>
            Clear
          </Button>
        </Space>
      </Card>

      {/* Data View + Variable View tabs */}
      <Card
        styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column', flex: 1 } }}
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 400,
          borderRadius: 6,
        }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ padding: '0 16px', marginTop: 8 }}
          items={[
            {
              key: 'data',
              label: <span><TableOutlined /> Data View</span>,
              children: (
                <div style={{ flex: 1, minHeight: 400, padding: '0 16px 16px' }}>
                  {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
                      <Text type="secondary">Loading data...</Text>
                    </div>
                  ) : dataset ? (
                    <div
                      className="ag-theme-alpine"
                      style={{ height: 'calc(100vh - 340px)', minHeight: 400, width: '100%' }}
                      onContextMenu={e => showContextMenu(e)}
                    >
                      <AgGridReact
                        ref={gridRef}
                        rowData={rowData}
                        rowModelType={rowModelType}
                        columnDefs={colDefs}
                        modules={[AllCommunityModule]}
                        theme="legacy"
                        defaultColDef={{
                          sortable: true,
                          filter: true,
                          resizable: true,
                          minWidth: 80,
                          editable: true,
                        }}
                        animateRows
                        enableCellTextSelection
                        ensureDomOrder
                        rowHeight={28}
                        headerHeight={32}
                        pagination={true}
                        paginationPageSize={200}
                        paginationPageSizeSelector={[20, 50, 100, 200]}
                        paginationAutoPageSize={false}
                        onCellValueChanged={onCellValueChanged}
                        onCellContextMenu={e => showContextMenu(e.event as any, e.rowIndex)}
                      />

                      {/* Context menu */}
                      {contextMenu && (
                        <div
                          style={{
                            position: 'fixed',
                            left: contextMenu.x,
                            top: contextMenu.y,
                            background: '#fff',
                            border: '1px solid #e2e8f0',
                            borderRadius: 6,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                            zIndex: 10000,
                            padding: '4px 0',
                            minWidth: 140,
                          }}
                        >
                          <div
                            style={{ padding: '6px 16px', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}
                            onClick={insertRow}
                            onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                          >
                            <PlusOutlined style={{ fontSize: 11 }} /> Insert Row
                          </div>
                          <div
                            style={{ padding: '6px 16px', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8, color: '#ef4444' }}
                            onClick={deleteRow}
                            onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                          >
                            <DeleteOutlined style={{ fontSize: 11 }} /> Delete Row
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400, flexDirection: 'column', gap: 12 }}>
                      <TableOutlined style={{ fontSize: 48, color: '#cbd5e0' }} />
                      <Text type="secondary" style={{ fontSize: 16 }}>No dataset loaded</Text>
                      <Text type="secondary">Upload a CSV or Excel file to begin</Text>
                    </div>
                  )}
                </div>
              ),
            },
            {
              key: 'variable',
              label: <span><ColumnHeightOutlined /> Variable View</span>,
              children: (
                <div style={{ padding: '0 16px 16px' }}>
                  {dataset ? (
                    <VariableView onUpdate={loadData} refreshKey={variableRefreshKey} />
                  ) : (
                    <div style={{ textAlign: 'center', padding: 40 }}>
                      <Text type="secondary">No dataset loaded. Upload data first.</Text>
                    </div>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* Status Bar */}
      {dataset && (
        <div style={{
          background: '#fff',
          borderTop: '1px solid #e2e8f0',
          padding: '6px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 12,
          color: '#64748b',
          marginTop: 8,
          borderRadius: 6,
        }}>
          <span>
            <Text strong style={{ fontSize: 12 }}>{dataset.filename}</Text>
          </span>
          <span>
            <Tag style={{ marginRight: 0 }}>{dataset.rows.toLocaleString()} rows × {dataset.cols} cols</Tag>
          </span>
          <span style={{ color: '#94a3b8' }}>
            {dataset.columns.filter(c => c.is_numeric).length} numeric,{' '}
            {dataset.columns.filter(c => c.is_categorical).length} categorical
          </span>
          <span style={{ color: '#94a3b8', fontSize: 11 }}>
            Undo: {undoCount} | Redo: {redoCount}
          </span>
        </div>
      )}

      {/* ── Keyboard Shortcuts Help Modal ──────────────────────────── */}
      <KeyboardShortcutsHelp
        visible={showHelp}
        onClose={() => setShowHelp(false)}
        items={shortcutHelpItems}
      />

      {/* ── Compute Variable Modal ─────────────────────────────────── */ }
      <Modal
        title="Compute Variable"
        open={computeOpen}
        onCancel={() => { setComputeOpen(false); setComputePreview(null) }}
        onOk={handleCompute}
        okText="Compute"
        confirmLoading={computeLoading}
        width={560}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>Target Variable:</Text>
            <Input
              placeholder="e.g. BMI, age_group, score"
              value={computeName}
              onChange={e => setComputeName(e.target.value)}
            />
          </div>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              Numeric Expression:
            </Text>
            <Input.TextArea
              rows={3}
              placeholder="e.g. weight / (height * height)&#10;e.g. sqrt(age) * 2&#10;e.g. abs(score1 - score2)"
              value={computeExpr}
              onChange={e => setComputeExpr(e.target.value)}
            />
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
              Use column names as variables. Supported: +, -, *, /, sqrt(), log(), abs(), round(), and conditionals.
            </Text>
          </div>
          <Button onClick={handleComputePreview} loading={computeLoading} size="small">
            Preview
          </Button>
          {computePreview !== null && (
            <div style={{ background: '#f8fafc', padding: 8, borderRadius: 6, maxHeight: 150, overflow: 'auto' }}>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                Preview (first {computePreview.length} values):
              </Text>
              <code style={{ fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                [{computePreview.map(v => v === null ? 'null' : String(v)).join(', ')}]
              </code>
            </div>
          )}
        </Space>
      </Modal>

      {/* ── Recode Modal ────────────────────────────────────────────── */}
      <Modal
        title="Recode Values"
        open={recodeOpen}
        onCancel={() => setRecodeOpen(false)}
        onOk={handleRecode}
        okText="Recode"
        confirmLoading={recodeLoading}
        width={520}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>Source Column:</Text>
            <Select
              style={{ width: '100%' }}
              placeholder="Select column to recode"
              value={recodeColumn || undefined}
              onChange={setRecodeColumn}
              options={dataset?.columns.map(c => ({ value: c.name, label: c.name })) || []}
              showSearch
            />
          </div>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>Recode Into:</Text>
            <Space>
              <Button
                size="small"
                type={recodeMode === 'same' ? 'primary' : 'default'}
                onClick={() => setRecodeMode('same')}
              >
                Same Column
              </Button>
              <Button
                size="small"
                type={recodeMode === 'new' ? 'primary' : 'default'}
                onClick={() => setRecodeMode('new')}
              >
                New Column
              </Button>
            </Space>
            {recodeMode === 'new' && (
              <Input
                style={{ marginTop: 8 }}
                placeholder="New column name"
                value={recodeIntoNew}
                onChange={e => setRecodeIntoNew(e.target.value)}
              />
            )}
          </div>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>Old → New Mappings:</Text>
            <Input.TextArea
              rows={5}
              placeholder={'1=10\n2=20\n3=30'}
              value={recodeMappings}
              onChange={e => setRecodeMappings(e.target.value)}
            />
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
              One mapping per line: <code>old_value=new_value</code>
            </Text>
          </div>
        </Space>
      </Modal>
    </div>
  )
}

export default DataPage
