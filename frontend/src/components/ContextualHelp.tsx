import React, { useState } from 'react'
import { Button, Popover, Typography, Space } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'

const { Text } = Typography

interface Props {
  title: string
  content: string
  expanded?: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
  style?: React.CSSProperties
}

const ContextualHelp: React.FC<Props> = ({ title, content, expanded, placement = 'top', style }) => {
  const [showMore, setShowMore] = useState(false)

  return (
    <Popover
      placement={placement}
      trigger="click"
      overlayStyle={{ maxWidth: 320 }}
      title={<Text strong>{title}</Text>}
      content={
        <div>
          <Text style={{ fontSize: 13 }}>{content}</Text>
          {expanded && (
            <>
              {showMore && (
                <div style={{ marginTop: 8, padding: 8, background: '#f8fafc', borderRadius: 4 }}>
                  <Text style={{ fontSize: 12, color: '#555' }}>{expanded}</Text>
                </div>
              )}
              <div style={{ marginTop: 6 }}>
                <Button type="link" size="small" style={{ padding: 0 }} onClick={() => setShowMore(!showMore)}>
                  {showMore ? 'Show less' : 'Learn more'}
                </Button>
              </div>
            </>
          )}
        </div>
      }
    >
      <QuestionCircleOutlined style={{ color: '#a0aec0', cursor: 'pointer', fontSize: 14, ...style }} />
    </Popover>
  )
}

export default ContextualHelp
