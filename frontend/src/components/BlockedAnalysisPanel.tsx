import React from 'react'
import { Card, Tag, Typography, Space, Popover, Badge } from 'antd'
import { StopOutlined, WarningFilled, InfoCircleOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { getHelpText } from '../utils/helpTerms'

const { Text, Title, Paragraph } = Typography

const COLORS = {
  primary: '#005eb8',
  danger: '#c62828',
  dangerBg: '#ffebee',
  warning: '#e65100',
  warningBg: '#fff3e0',
  muted: '#666',
  border: '#e8e8e8',
}

export interface BlockedResult {
  blocked: boolean
  eligible: boolean
  requested_action?: string
  action_type?: string
  reason?: string
  details?: string
  triggering_data_properties?: string[]
  suggested_alternatives?: string[]
  alternative_ranked?: {
    preferred?: string[]
    acceptable?: string[]
    advanced?: string[]
  }
  help_terms?: string[]
}

interface BlockedAnalysisPanelProps {
  result: BlockedResult
}

const HelpTermPopover: React.FC<{ term: string }> = ({ term }) => {
  const helpText = getHelpText(term)
  if (!helpText) return null
  return (
    <Popover
      title={term.replace(/_/g, ' ')}
      content={<Text style={{ fontSize: 13 }}>{helpText}</Text>}
      trigger="hover"
      placement="right"
    >
      <button
        aria-label={`Learn more about ${term.replace(/_/g, ' ')}`}
        style={{
          border: 'none', background: 'none', cursor: 'pointer',
          padding: '0 4px', color: COLORS.primary, fontSize: 14,
          verticalAlign: 'middle',
        }}
      >
        <QuestionCircleOutlined />
      </button>
    </Popover>
  )
}

const RankedAlternatives: React.FC<{ ranked: NonNullable<BlockedResult['alternative_ranked']> }> = ({ ranked }) => {
  const sections = [
    { label: 'Preferred', key: 'preferred' as const, color: '#52c41a' },
    { label: 'Acceptable', key: 'acceptable' as const, color: '#faad14' },
    { label: 'Advanced', key: 'advanced' as const, color: '#1890ff' },
  ]
  return (
    <div style={{ marginTop: 12 }}>
      <Text strong style={{ fontSize: 14, color: '#333' }}>Suggested alternatives</Text>
      {sections.map(({ label, key, color }) => {
        const items = ranked[key] ?? []
        return (
          <div key={key} style={{ display: 'flex', alignItems: 'baseline', marginTop: 6, gap: 8 }}>
            <Badge color={color} text={<Text type="secondary" style={{ fontSize: 13, minWidth: 80, fontWeight: 500 }}>{label}:</Text>} />
            <Text style={{ fontSize: 13 }}>
              {items.length > 0 ? items.join(', ') : <Text type="secondary" italic>none</Text>}
            </Text>
          </div>
        )
      })}
    </div>
  )
}

const BlockedAnalysisPanel: React.FC<BlockedAnalysisPanelProps> = ({ result }) => {
  const { requested_action, action_type, reason, details, triggering_data_properties, suggested_alternatives, alternative_ranked, help_terms } = result

  return (
    <Card
      aria-label={`Blocked analysis: ${requested_action || 'Unknown'}`}
      role="region"
      style={{
        borderLeft: `4px solid ${COLORS.danger}`,
        borderRadius: 6,
        margin: '16px 0',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div
          aria-hidden="true"
          style={{
            width: 32, height: 32, borderRadius: '50%',
            background: COLORS.dangerBg, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
          }}
        >
          <StopOutlined style={{ color: COLORS.danger, fontSize: 18 }} />
        </div>
        <div style={{ flex: 1 }}>
          <Text strong style={{ fontSize: 15, color: '#222' }}>
            {requested_action || 'Analysis'}
          </Text>
          <div>
            {action_type && <Tag style={{ fontSize: 11, marginRight: 4 }}>{action_type}</Tag>}
            <Tag color="warning" icon={<WarningFilled />}>Blocked</Tag>
          </div>
        </div>
      </div>

      {/* Reason */}
      {reason && (
        <div style={{ background: COLORS.dangerBg, borderRadius: 4, padding: '8px 12px', marginBottom: 10 }}>
          <Space>
            <WarningFilled style={{ color: COLORS.danger }} />
            <Text style={{ color: '#333', fontSize: 13 }}>{reason}</Text>
          </Space>
        </div>
      )}

      {/* Details */}
      {details && (
        <div style={{ marginBottom: 10 }}>
          <Space>
            <InfoCircleOutlined style={{ color: COLORS.primary }} />
            <Text type="secondary" style={{ fontSize: 13 }}>{details}</Text>
          </Space>
        </div>
      )}

      {/* Triggering properties */}
      {triggering_data_properties && triggering_data_properties.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Triggering properties:</Text>
          <Space size={4} wrap>
            {triggering_data_properties.map((prop) => (
              <Tag key={prop} style={{ fontSize: 11, borderRadius: 3 }} color="default">{prop}</Tag>
            ))}
          </Space>
        </div>
      )}

      {/* Alternatives */}
      {alternative_ranked ? (
        <RankedAlternatives ranked={alternative_ranked} />
      ) : suggested_alternatives && suggested_alternatives.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <Text strong style={{ fontSize: 14, color: '#333' }}>Suggested alternatives</Text>
          <ol style={{ margin: '6px 0 0 0', paddingLeft: 20 }}>
            {suggested_alternatives.map((alt, i) => (
              <li key={i}><Text style={{ fontSize: 13 }}>{alt}</Text></li>
            ))}
          </ol>
        </div>
      ) : null}

      {/* Help terms */}
      {help_terms && help_terms.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${COLORS.border}` }}>
          <Text type="secondary" style={{ fontSize: 12 }}>Help:</Text>
          <Space size={4} wrap style={{ marginLeft: 4 }}>
            {help_terms.map((term) => (
              <span key={term}>
                <Text code style={{ fontSize: 11, background: '#f5f5f5' }}>{term.replace(/_/g, ' ')}</Text>
                <HelpTermPopover term={term} />
              </span>
            ))}
          </Space>
        </div>
      )}
    </Card>
  )
}

export default BlockedAnalysisPanel
export { BlockedAnalysisPanel }
