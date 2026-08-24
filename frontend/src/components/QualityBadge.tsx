import React from 'react'
import { Alert, Tag, Tooltip } from 'antd'
import { CheckCircleOutlined, SafetyCertificateOutlined, WarningOutlined } from '@ant-design/icons'

interface QA {
  status?: 'ok' | 'warning' | 'error'
  warnings?: string[]
  auto?: string[]
  analysis?: string
}

export function QualityBadge({ qa, compact }: { qa?: QA | null; compact?: boolean }) {
  if (!qa) return null

  // Hidden success indicator only.
  if (qa.status === 'ok' && (!qa.warnings || qa.warnings.length === 0)) {
    return (
      <Tooltip title="This result passed automatic quality control. No corrections were needed.">
        <Tag color="success" icon={<CheckCircleOutlined />} style={{ marginBottom: 8 }}>
          Quality check passed
        </Tag>
      </Tooltip>
    )
  }

  const auto = qa.auto || []
  const warnings = qa.warnings || []

  return (
    <Alert
      type={qa.status === 'error' ? 'error' : 'warning'}
      showIcon
      icon={qa.status === 'error' ? <WarningOutlined /> : <SafetyCertificateOutlined />}
      message={qa.status === 'error' ? 'Could not produce a valid result' : 'Quality control'}
      description={
        <div style={{ fontSize: 12, lineHeight: 1.6 }}>
          {warnings.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
          {auto.length > 0 && (
            <div style={{ marginTop: 6 }}>
              <Tag color="blue" style={{ marginBottom: 4 }}>
                Auto-corrected ({auto.length})
              </Tag>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {auto.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}
        </div>
      }
      style={{ marginBottom: 12 }}
    />
  )
}

export default QualityBadge
