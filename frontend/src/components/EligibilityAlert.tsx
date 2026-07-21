import React from 'react'
import { Alert, Space, Button, Typography } from 'antd'
import { BulbOutlined } from '@ant-design/icons'
import type { EligibilityResult } from '../hooks/useEligibility'

const { Text } = Typography

interface Props {
  result: EligibilityResult
  onSelectAlternative?: (name: string) => void
  style?: React.CSSProperties
}

const EligibilityAlert: React.FC<Props> = ({ result, onSelectAlternative, style }) => {
  if (result.eligible || !result.blocked) return null

  const suggestions = [
    ...(result.alternative_ranked?.preferred || []),
    ...(result.alternative_ranked?.acceptable || []),
    ...(result.suggested_alternatives || []),
  ]

  return (
    <Alert
      type="warning"
      showIcon
      icon={<BulbOutlined />}
      message={
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Text strong>{result.reason || 'This selection is not suitable.'}</Text>
          {result.details && (
            <Text type="secondary" style={{ fontSize: 12 }}>{result.details}</Text>
          )}
          {suggestions.length > 0 && (
            <div>
              <Text style={{ fontSize: 12, fontWeight: 600 }}>Try instead: </Text>
              <Space wrap size={4} style={{ marginTop: 4 }}>
                {suggestions.map((s, i) => (
                  <Button
                    key={i}
                    type="link"
                    size="small"
                    style={{ padding: '0 4px', fontSize: 12 }}
                    onClick={() => onSelectAlternative?.(s)}
                  >
                    {s}
                  </Button>
                ))}
              </Space>
            </div>
          )}
        </Space>
      }
      style={{ marginBottom: 12, ...style }}
    />
  )
}

export default EligibilityAlert
