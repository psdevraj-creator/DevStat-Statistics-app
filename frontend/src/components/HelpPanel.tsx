import React, { useState, useMemo } from 'react'
import { Drawer, Input, Typography, Collapse, Tag, Space, Divider, List, Empty, Button } from 'antd'
import { SearchOutlined, QuestionCircleOutlined, BookOutlined, ExperimentOutlined, BarChartOutlined, FileTextOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { getPageHelp, getQuickStart, getChartInterpretation, searchHelp, getAllGlossary, getAllFAQ } from '../utils/helpContent'

const { Text, Title } = Typography

interface Props {
  open: boolean
  onClose: () => void
  initialSection?: string
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  page: <FileTextOutlined />,
  section: <FileTextOutlined />,
  chart: <BarChartOutlined />,
  glossary: <BookOutlined />,
  faq: <QuestionCircleOutlined />,
}

const HelpPanel: React.FC<Props> = ({ open, onClose, initialSection }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<string>('context')

  const pageHelp = getPageHelp(location.pathname)
  const searchResults = useMemo(() => searchQuery.length >= 2 ? searchHelp(searchQuery) : [], [searchQuery])
  const glossary = getAllGlossary()
  const faqs = getAllFAQ()
  const quickStart = getQuickStart()

  const groupedGlossary = useMemo(() => {
    const groups: Record<string, typeof glossary> = {}
    for (const entry of glossary) {
      if (!groups[entry.category]) groups[entry.category] = []
      groups[entry.category].push(entry)
    }
    return groups
  }, [])

  const tabs = [
    { key: 'context', label: 'Help', icon: <QuestionCircleOutlined /> },
    { key: 'quickstart', label: 'Quick Start', icon: <ExperimentOutlined /> },
    { key: 'glossary', label: 'Glossary', icon: <BookOutlined /> },
    { key: 'faq', label: 'FAQ', icon: <QuestionCircleOutlined /> },
  ]

  const renderContextHelp = () => (
    <div style={{ padding: '0 4px' }}>
      {pageHelp && (
        <>
          <Title level={5} style={{ marginTop: 0 }}>{pageHelp.title}</Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>{pageHelp.description}</Text>
          {pageHelp.quickStart && (
            <div style={{ background: '#f0f7ff', borderRadius: 6, padding: '8px 12px', marginBottom: 16 }}>
              <Text strong style={{ fontSize: 12, color: '#005eb8' }}>Quick steps:</Text>
              {pageHelp.quickStart.map((s, i) => (
                <div key={i} style={{ fontSize: 12, marginTop: 4, color: '#333' }}>{i + 1}. {s}</div>
              ))}
            </div>
          )}
          <Collapse ghost size="small" items={pageHelp.sections.map(s => ({
            key: s.title,
            label: <Text strong>{s.title}</Text>,
            children: (
              <div>
                <Text style={{ fontSize: 13 }}>{s.content}</Text>
                {s.expanded && (
                  <>
                    <Divider style={{ margin: '8px 0' }} />
                    <Text style={{ fontSize: 12, color: '#555' }}>{s.expanded}</Text>
                  </>
                )}
              </div>
            ),
          }))} />
          {pageHelp.relatedPages && pageHelp.relatedPages.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Text strong style={{ fontSize: 12 }}>Related pages: </Text>
              <Space wrap size={4} style={{ marginTop: 4 }}>
                {pageHelp.relatedPages.map(p => (
                  <Tag key={p} color="blue" style={{ cursor: 'pointer' }} onClick={() => { navigate(p); onClose() }}>
                    {p.replace('/analyze/', '').replace('/', '') || 'Data View'}
                  </Tag>
                ))}
              </Space>
            </div>
          )}
        </>
      )}
      {!pageHelp && (
        <Text type="secondary">Select a page to see context-specific help.</Text>
      )}
    </div>
  )

  const renderQuickStart = () => (
    <div style={{ padding: '0 4px' }}>
      <Title level={5} style={{ marginTop: 0 }}>Getting Started</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Follow these steps to get your first analysis done in under 5 minutes.
      </Text>
      {quickStart.map(s => (
        <div key={s.step} style={{ display: 'flex', gap: 12, marginBottom: 16, background: '#f8fafc', borderRadius: 8, padding: '12px 16px' }}>
          <div style={{ width: 28, height: 28, borderRadius: 14, background: '#005eb8', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, flexShrink: 0 }}>{s.step}</div>
          <div>
            <Text strong>{s.title}</Text>
            <div style={{ fontSize: 12, color: '#555', marginTop: 2 }}>{s.description}</div>
            <div style={{ fontSize: 11, color: '#005eb8', marginTop: 4, fontStyle: 'italic' }}>{s.action}</div>
          </div>
        </div>
      ))}
    </div>
  )

  const renderGlossary = () => (
    <div style={{ padding: '0 4px' }}>
      <Title level={5} style={{ marginTop: 0 }}>Glossary</Title>
      {Object.entries(groupedGlossary).map(([category, entries]) => (
        <div key={category} style={{ marginBottom: 16 }}>
          <Tag color="blue" style={{ marginBottom: 8, textTransform: 'capitalize' }}>{category}</Tag>
          {entries.map(e => (
            <div key={e.term} style={{ marginBottom: 8, padding: '6px 8px', background: '#f8fafc', borderRadius: 4 }}>
              <Text strong style={{ fontSize: 12 }}>{e.term}</Text>
              <div style={{ fontSize: 11, color: '#555', marginTop: 2 }}>{e.definition}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )

  const renderFAQ = () => (
    <div style={{ padding: '0 4px' }}>
      <Title level={5} style={{ marginTop: 0 }}>Frequently Asked Questions</Title>
      <Collapse ghost size="small" items={faqs.map(f => ({
        key: f.question,
        label: <Text style={{ fontSize: 13 }}>{f.question}</Text>,
        children: <Text style={{ fontSize: 13 }}>{f.answer}</Text>,
      }))} />
    </div>
  )

  const renderSearch = () => {
    if (!searchQuery || searchQuery.length < 2) return null
    if (searchResults.length === 0) return <Empty description="No results found" style={{ padding: 24 }} />
    return (
      <List
        size="small"
        dataSource={searchResults}
        renderItem={item => (
          <List.Item style={{ cursor: item.path ? 'pointer' : 'default' }} onClick={() => { if (item.path) { navigate(item.path); onClose() } }}>
            <List.Item.Meta
              avatar={TYPE_ICONS[item.type]}
              title={<Text style={{ fontSize: 13 }}>{item.title}</Text>}
              description={<Text style={{ fontSize: 11 }}>{item.content.slice(0, 120)}</Text>}
            />
          </List.Item>
        )}
      />
    )
  }

  return (
    <Drawer
      title={
        <Space>
          <QuestionCircleOutlined style={{ color: '#005eb8' }} />
          <span>Help</span>
        </Space>
      }
      placement="right"
      width={400}
      open={open}
      onClose={onClose}
      extra={<Button type="text" onClick={onClose}>✕</Button>}
    >
      <Input
        prefix={<SearchOutlined />}
        placeholder="Search help..."
        value={searchQuery}
        onChange={e => setSearchQuery(e.target.value)}
        allowClear
        style={{ marginBottom: 16 }}
      />

      {searchQuery.length >= 2 ? renderSearch() : (
        <>
          <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap' }}>
            {tabs.map(t => (
              <Button
                key={t.key}
                size="small"
                type={activeTab === t.key ? 'primary' : 'default'}
                icon={t.icon}
                onClick={() => setActiveTab(t.key)}
                style={{ fontSize: 12 }}
              >
                {t.label}
              </Button>
            ))}
          </div>

          {activeTab === 'context' && renderContextHelp()}
          {activeTab === 'quickstart' && renderQuickStart()}
          {activeTab === 'glossary' && renderGlossary()}
          {activeTab === 'faq' && renderFAQ()}
        </>
      )}
    </Drawer>
  )
}

export default HelpPanel
