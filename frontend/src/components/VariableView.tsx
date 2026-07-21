/**
 * VariableView — SPSS-like Variable View table
 *
 * Displays and allows editing of variable metadata in a spreadsheet-style
 * table, just like SPSS's Variable View tab.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { Input, Select, InputNumber, Button, Tag, Space, Tooltip, message, Modal, Table, Typography } from 'antd'
import { EditOutlined, PlusOutlined, DeleteOutlined, SaveOutlined, CloseOutlined, ReloadOutlined } from '@ant-design/icons'
import { datasetApi } from '../api/client'

const { Text } = Typography

// ── Types ────────────────────────────────────────────────────────────────

interface VariableMeta {
  name: string
  type: string
  width: number
  decimals: number
  label: string
  value_labels: Record<string, string>
  missing_values: any[]
  columns: number
  align: string
  measure: string
  role: string
  // Computed
  dtype?: string
  unique_count?: number
  missing_count?: number
  missing_pct?: number
}

interface VariableViewProps {
  /** Called after any metadata update */
  onUpdate?: () => void
  /** External trigger to refresh */
  refreshKey?: number
}

// ── Type options matching SPSS ───────────────────────────────────────────

const TYPE_OPTIONS = [
  { value: 'numeric', label: 'Numeric' },
  { value: 'string', label: 'String' },
  { value: 'date', label: 'Date' },
  { value: 'comma', label: 'Comma' },
  { value: 'dot', label: 'Dot' },
  { value: 'dollar', label: 'Dollar' },
  { value: 'percent', label: 'Percent' },
]

const MEASURE_OPTIONS = [
  { value: 'scale', label: 'Scale (numeric)' },
  { value: 'ordinal', label: 'Ordinal' },
  { value: 'nominal', label: 'Nominal' },
]

const ALIGN_OPTIONS = [
  { value: 'left', label: 'Left' },
  { value: 'center', label: 'Center' },
  { value: 'right', label: 'Right' },
]

const ROLE_OPTIONS = [
  { value: 'input', label: 'Input' },
  { value: 'target', label: 'Target' },
  { value: 'both', label: 'Both' },
  { value: 'none', label: 'None' },
  { value: 'partition', label: 'Partition' },
  { value: 'split', label: 'Split' },
]

// ── Component ────────────────────────────────────────────────────────────

const VariableView: React.FC<VariableViewProps> = ({ onUpdate, refreshKey = 0 }) => {
  const [variables, setVariables] = useState<VariableMeta[]>([])
  const [loading, setLoading] = useState(false)
  const [editingCell, setEditingCell] = useState<{ row: number; field: string } | null>(null)
  const [editValue, setEditValue] = useState<any>(null)

  const loadVariables = useCallback(async () => {
    setLoading(true)
    try {
      const res = await datasetApi.variableView()
      setVariables(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      // Silently handle — no data loaded is fine
      setVariables([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadVariables()
  }, [refreshKey, loadVariables])

  const startEdit = (row: number, field: string, currentValue: any) => {
    setEditingCell({ row, field })
    setEditValue(currentValue)
  }

  const cancelEdit = () => {
    setEditingCell(null)
    setEditValue(null)
  }

  const saveEdit = async (row: number, field: string) => {
    const varName = variables[row].name
    try {
      await datasetApi.updateVariable(varName, { [field]: editValue })
      message.success(`Updated ${varName} → ${field}`)
      setEditingCell(null)
      setEditValue(null)
      loadVariables()
      onUpdate?.()
    } catch (err: any) {
      message.error('Failed to update: ' + (err?.response?.data?.detail || err.message))
    }
  }

  const handleValueLabels = (varName: string) => {
    const v = variables.find(x => x.name === varName)
    if (!v) return

    const labels = v.value_labels || {}
    const labelsStr = Object.entries(labels)
      .map(([k, v]) => `${k}=${v}`)
      .join('\n')

    let textareaValue = labelsStr
    const textareaRef = React.createRef<any>()

    Modal.confirm({
      title: `Value Labels for ${varName}`,
      content: (
        <div>
          <p style={{ marginBottom: 8, fontSize: 12, color: '#64748b' }}>
            Enter one label per line: <code>value=label</code>
          </p>
          <Input.TextArea
            ref={textareaRef}
            defaultValue={labelsStr}
            onChange={e => { textareaValue = e.target.value }}
            rows={6}
            placeholder="1=Male&#10;2=Female"
          />
        </div>
      ),
      onOk: async () => {
        const newLabels: Record<string, string> = {}
        textareaValue.split('\n').forEach(line => {
          const eqIdx = line.indexOf('=')
          if (eqIdx > 0) {
            newLabels[line.substring(0, eqIdx).trim()] = line.substring(eqIdx + 1).trim()
          }
        })
        try {
          await datasetApi.setValueLabels(varName, newLabels)
          message.success('Value labels saved')
          loadVariables()
        } catch (err: any) {
          message.error('Failed: ' + (err?.response?.data?.detail || err.message))
        }
      },
    })
  }

  const handleMissingValues = (varName: string) => {
    const v = variables.find(x => x.name === varName)
    if (!v) return

    const mv = v.missing_values || []
    const mvStr = mv.join(', ')

    Modal.confirm({
      title: `Missing Values for ${varName}`,
      content: (
        <div>
          <p style={{ marginBottom: 8, fontSize: 12, color: '#64748b' }}>
            Enter missing value codes separated by commas. These values will be treated as user-missing in analyses.
          </p>
          <Input
            id="missing-values-input"
            defaultValue={mvStr}
            placeholder="e.g. -99, 999, NA"
          />
        </div>
      ),
      onOk: async () => {
        const input = document.getElementById('missing-values-input') as HTMLInputElement
        const text = input?.value || ''
        const newMissing = text
          .split(',')
          .map(s => s.trim())
          .filter(s => s.length > 0)
        try {
          await datasetApi.setMissingValues(varName, newMissing)
          message.success('Missing values saved')
          loadVariables()
        } catch (err: any) {
          message.error('Failed: ' + (err?.response?.data?.detail || err.message))
        }
      },
    })
  }

  const handleDeleteVariable = (varName: string) => {
    Modal.confirm({
      title: `Delete column "${varName}"?`,
      content: 'This will permanently remove the column and all its data. This cannot be undone via undo.',
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await datasetApi.deleteColumn(varName)
          message.success(`Deleted column "${varName}"`)
          loadVariables()
          onUpdate?.()
        } catch (err: any) {
          message.error('Delete failed: ' + (err?.response?.data?.detail || err.message))
        }
      },
    })
  }

  const renderCell = (text: any, record: VariableMeta, rowIdx: number, field: string) => {
    const isEditing = editingCell?.row === rowIdx && editingCell?.field === field

    if (isEditing) {
      // Render editor based on field type
      if (field === 'type') {
        return (
          <Space>
            <Select
              value={editValue}
              onChange={setEditValue}
              options={TYPE_OPTIONS}
              style={{ width: 100 }}
              size="small"
              autoFocus
            />
            <Button size="small" type="link" icon={<SaveOutlined />} onClick={() => saveEdit(rowIdx, field)} />
            <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
          </Space>
        )
      }
      if (field === 'measure') {
        return (
          <Space>
            <Select
              value={editValue}
              onChange={setEditValue}
              options={MEASURE_OPTIONS}
              style={{ width: 140 }}
              size="small"
              autoFocus
            />
            <Button size="small" type="link" icon={<SaveOutlined />} onClick={() => saveEdit(rowIdx, field)} />
            <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
          </Space>
        )
      }
      if (field === 'align') {
        return (
          <Space>
            <Select
              value={editValue}
              onChange={setEditValue}
              options={ALIGN_OPTIONS}
              style={{ width: 100 }}
              size="small"
              autoFocus
            />
            <Button size="small" type="link" icon={<SaveOutlined />} onClick={() => saveEdit(rowIdx, field)} />
            <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
          </Space>
        )
      }
      if (field === 'role') {
        return (
          <Space>
            <Select
              value={editValue}
              onChange={setEditValue}
              options={ROLE_OPTIONS}
              style={{ width: 100 }}
              size="small"
              autoFocus
            />
            <Button size="small" type="link" icon={<SaveOutlined />} onClick={() => saveEdit(rowIdx, field)} />
            <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
          </Space>
        )
      }
      if (field === 'width' || field === 'decimals' || field === 'columns') {
        return (
          <Space>
            <InputNumber
              value={editValue}
              onChange={setEditValue}
              min={1}
              max={255}
              size="small"
              style={{ width: 70 }}
              autoFocus
            />
            <Button size="small" type="link" icon={<SaveOutlined />} onClick={() => saveEdit(rowIdx, field)} />
            <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
          </Space>
        )
      }
      // Default: text input
      return (
        <Space>
          <Input
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            size="small"
            style={{ width: field === 'label' ? 200 : 120 }}
            autoFocus
          />
          <Button size="small" type="link" icon={<SaveOutlined />} onClick={() => saveEdit(rowIdx, field)} />
          <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancelEdit} />
        </Space>
      )
    }

    // Display mode
    const displayVal = text ?? ''
    if (field === 'value_labels') {
      const labels = record.value_labels || {}
      const labelCount = Object.keys(labels).length
      return (
        <Tooltip title={Object.entries(labels).map(([k, v]) => `${k} = ${v}`).join('\n')}>
          <Button
            type="link"
            size="small"
            onClick={() => handleValueLabels(record.name)}
          >
            {labelCount > 0 ? (
              <Tag color="blue">{labelCount} label{labelCount > 1 ? 's' : ''}</Tag>
            ) : (
              <Tag>{labelCount === 0 ? 'None' : '...'}</Tag>
            )}
          </Button>
        </Tooltip>
      )
    }
    if (field === 'missing_values') {
      const mv = record.missing_values || []
      return (
        <Tooltip title={mv.length > 0 ? `Missing codes: ${mv.join(', ')}` : 'Click to define missing values'}>
          <Button
            type="link"
            size="small"
            onClick={() => handleMissingValues(record.name)}
          >
            {mv.length > 0 ? (
              <Tag color="orange">{mv.length} code{mv.length > 1 ? 's' : ''}</Tag>
            ) : (
              <Tag>None</Tag>
            )}
          </Button>
        </Tooltip>
      )
    }
    if (field === 'type') {
      return <Tag color={displayVal === 'numeric' ? 'blue' : displayVal === 'string' ? 'green' : 'orange'}>{displayVal}</Tag>
    }
    if (field === 'measure') {
      return <Tag>{displayVal}</Tag>
    }

    return (
      <span
        style={{ cursor: 'pointer', minHeight: 24, display: 'inline-block', width: '100%' }}
        onDoubleClick={() => startEdit(rowIdx, field, text)}
        title="Double-click to edit"
      >
        {displayVal || <span style={{ color: '#cbd5e0' }}>—</span>}
      </span>
    )
  }

  const columns = [
    {
      title: '#',
      key: 'index',
      width: 40,
      fixed: 'left' as const,
      render: (_: any, __: any, idx: number) => (
        <span style={{ color: '#94a3b8', fontSize: 11 }}>{idx + 1}</span>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 120,
      render: (text: string, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'name'),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (text: string, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'type'),
    },
    {
      title: 'Width',
      dataIndex: 'width',
      key: 'width',
      width: 70,
      render: (text: number, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'width'),
    },
    {
      title: 'Decimals',
      dataIndex: 'decimals',
      key: 'decimals',
      width: 80,
      render: (text: number, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'decimals'),
    },
    {
      title: 'Label',
      dataIndex: 'label',
      key: 'label',
      width: 200,
      ellipsis: true,
      render: (text: string, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'label'),
    },
    {
      title: 'Values',
      dataIndex: 'value_labels',
      key: 'value_labels',
      width: 100,
      render: (text: any, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'value_labels'),
    },
    {
      title: 'Missing',
      dataIndex: 'missing_values',
      key: 'missing_values',
      width: 100,
      render: (text: any, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'missing_values'),
    },
    {
      title: 'Columns',
      key: 'col_width',
      width: 80,
      render: (text: any, record: VariableMeta, idx: number) => renderCell(record.columns, record, idx, 'columns'),
    },
    {
      title: 'Align',
      dataIndex: 'align',
      key: 'align',
      width: 90,
      render: (text: string, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'align'),
    },
    {
      title: 'Measure',
      dataIndex: 'measure',
      key: 'measure',
      width: 120,
      render: (text: string, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'measure'),
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      width: 90,
      render: (text: string, record: VariableMeta, idx: number) => renderCell(text, record, idx, 'role'),
    },
    {
      title: '',
      key: 'actions',
      width: 50,
      fixed: 'right' as const,
      render: (_: any, record: VariableMeta) => (
        <Tooltip title="Delete variable">
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteVariable(record.name)}
          />
        </Tooltip>
      ),
    },
  ]

  return (
    <div>
      <div style={{ padding: '8px 0', display: 'flex', gap: 8, alignItems: 'center' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {variables.length} variable{variables.length !== 1 ? 's' : ''}
        </Text>
        <span style={{ flex: 1 }} />
        <Button size="small" icon={<PlusOutlined />} onClick={async () => {
          const name = `var${variables.length + 1}`
          try {
            await datasetApi.addColumn(name)
            message.success(`Added column "${name}"`)
            loadVariables()
            onUpdate?.()
          } catch (err: any) {
            message.error('Failed: ' + (err?.response?.data?.detail || err.message))
          }
        }}>
          Add Variable
        </Button>
        <Button size="small" icon={<ReloadOutlined />} onClick={loadVariables}>
          Refresh
        </Button>
      </div>
      <Table
        dataSource={variables}
        columns={columns}
        rowKey="name"
        pagination={false}
        loading={loading}
        size="small"
        scroll={{ x: 1300, y: 'calc(100vh - 400px)' }}
        bordered
        style={{ fontSize: 13 }}
      />
    </div>
  )
}

export default VariableView
