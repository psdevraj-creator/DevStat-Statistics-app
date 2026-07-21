import React from 'react'
import { Typography, Card, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

const { Text, Title } = Typography

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo })
    console.error('DevStat Error Boundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, maxWidth: 600, margin: '80px auto' }}>
          <Card style={{ borderLeft: '4px solid #e53e3e' }}>
            <Title level={4} style={{ color: '#e53e3e' }}>Something went wrong</Title>
            <div style={{ background: '#f8fafc', padding: 16, borderRadius: 6, marginTop: 16, overflow: 'auto', maxHeight: 300 }}>
              <Text type="danger" strong>{this.state.error?.name}: </Text>
              <Text type="danger">{this.state.error?.message}</Text>
              {this.state.errorInfo && (
                <pre style={{ fontSize: 11, marginTop: 12, whiteSpace: 'pre-wrap' }}>
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </div>
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={() => window.location.reload()}
              style={{ marginTop: 16 }}
            >
              Reload Page
            </Button>
          </Card>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
