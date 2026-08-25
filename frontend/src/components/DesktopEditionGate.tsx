import React from 'react'
import { Tag, Tooltip } from 'antd'
import { DesktopOutlined } from '@ant-design/icons'

/** Desktop Edition banner + note. The Desktop Edition is the same DevStat app
 *  but its analysis engine runs entirely on this machine — the data is never
 *  sent anywhere. Sign-in, registration and subscription are online (shared with
 *  the online app), so you can register here and also use it online, and vice
 *  versa. When `enabled` is false (the online hosted app) this is a no-op. */
const DesktopEditionGate: React.FC<{ enabled: boolean; children: React.ReactNode }> = ({ enabled, children }) => {
  if (!enabled) return <>{children}</>
  return (
    <>
      <div
        style={{
          background: 'linear-gradient(135deg, #003d8b 0%, #005eb8 50%, #1a7fd4 100%)',
          color: '#fff',
          padding: '7px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 12.5,
          boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
        }}
      >
        <DesktopOutlined style={{ fontSize: 16 }} />
        <b>Desktop Edition</b>
        <span style={{ opacity: 0.9 }}>· analysis runs on this machine — your data never leaves it</span>
        <Tooltip title="Signing in, registering and your subscription happen online (and work on the online app too). No analysis data is ever uploaded.">
          <Tag style={{ marginLeft: 'auto', color: '#fff', background: 'rgba(255,255,255,0.18)', borderColor: 'rgba(255,255,255,0.35)', cursor: 'help' }}>
            Offline analysis · Online account
          </Tag>
        </Tooltip>
      </div>
      {children}
    </>
  )
}

export default DesktopEditionGate
