import React from 'react'
import { Alert, Typography, Space } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'

const { Text } = Typography

export interface ErrorInfo {
  error?: string
  message?: string
  detail?: string
  suggestion?: string
  help_topic?: string
}

interface Props {
  error: ErrorInfo | string | null | undefined
  style?: React.CSSProperties
}

const ErrorDisplay: React.FC<Props> = ({ error, style }) => {
  if (!error) return null

  const message = typeof error === 'string' ? error : (error.message || error.error || 'An error occurred')
  const detail = typeof error === 'string' ? '' : (error.detail || '')
  const suggestion = typeof error === 'string' ? '' : (error.suggestion || '')

  return (
    <Alert
      type="error"
      showIcon
      icon={<InfoCircleOutlined />}
      message={
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Text style={{ fontWeight: 600, fontSize: 13 }}>{message}</Text>
          {detail && (
            <Text style={{ fontSize: 12, color: '#555' }}>{detail}</Text>
          )}
          {suggestion && (
            <Text style={{ fontSize: 12, color: '#005eb8', fontStyle: 'italic' }}>
              💡 {suggestion}
            </Text>
          )}
        </Space>
      }
      style={{ marginBottom: 12, ...style }}
    />
  )
}

export default ErrorDisplay
