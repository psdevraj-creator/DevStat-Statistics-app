import React, { useState } from 'react'
import { Card, Tabs, Form, Input, Button, Typography, Space, Alert, message, Divider, App as AntApp } from 'antd'
import {
  GoogleOutlined, MailOutlined, LockOutlined, UserOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { firebaseConfigured, getFirebaseAuth } from '../lib/firebase'
import { authApi, storeDevStatSession } from '../api/authApi'
import { useAuth } from '../stores/authStore'

const { Title, Text } = Typography

export default function AuthPage() {
  const navigate = useNavigate()
  const { clearSession } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [verifyNotice, setVerifyNotice] = useState<string | null>(null)
  const auth = getFirebaseAuth()

  // Confirms an authenticated Firebase user against the backend and stores the
  // DevStat session (signed token + licence/usage entitlement from Firestore).
  async function finish(idToken: string, provider: 'google' | 'email') {
    const s = await authApi.session(idToken)
    // Desktop Edition: this login page was opened in a popup by the desktop app.
    // Hand the session back to the opener (desktop window) and close, so the
    // desktop logs in without any cross-origin API call.
    if (window.opener && new URLSearchParams(window.location.search).get('desktop') === '1') {
      window.opener.postMessage({ type: 'devstat-login', session: s }, '*')
      window.close()
      return
    }
    storeDevStatSession(s)
    message.success(provider === 'email' ? 'Signed in' : 'Welcome back')
    navigate('/')
  }

  async function handleEmail(values: { email: string; password: string; confirmPassword?: string }) {
    if (!firebaseConfigured) {
      message.warning('DevStat account login needs a Firebase project. Add its config to enable sign-in.')
      return
    }
    setLoading(true)
    try {
      const { signInWithEmailAndPassword, createUserWithEmailAndPassword, sendEmailVerification } = await import('firebase/auth')
      if (mode === 'register') {
        const cred = await createUserWithEmailAndPassword(auth, values.email, values.password)
        // Anti-bot: only email registrations require verification before use.
        await sendEmailVerification(cred.user)
        setVerifyNotice('Account created. We sent a verification link to your email — check your inbox AND your Spam/Junk folder (some providers route it there), then verify before signing in.')
        return
      }
      const cred = await signInWithEmailAndPassword(auth, values.email, values.password)
      if (!cred.user.emailVerified) {
        setVerifyNotice('Please verify your email first (a verification email was sent when you registered — check your inbox and your Spam/Junk folder). You can resend it below.')
        return
      }
      const token = await cred.user.getIdToken()
      await finish(token, 'email')
    } catch (e: any) {
      message.error(e?.message || 'Sign-in failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogle() {
    if (!firebaseConfigured) { message.warning('Add Firebase config to enable Google sign-in.'); return }
    setLoading(true)
    try {
      const { GoogleAuthProvider, signInWithPopup } = await import('firebase/auth')
      const cred = await signInWithPopup(auth, new GoogleAuthProvider())
      const token = await cred.user.getIdToken()
      await finish(token, 'google')
    } catch (e: any) {
      message.error(e?.message || 'Google sign-in failed')
    } finally { setLoading(false) }
   }
 

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg,#003d8b,#005eb8)', padding: 16 }}>
      <Card style={{ width: 400, maxWidth: '100%', borderRadius: 14, boxShadow: '0 16px 60px rgba(0,0,0,.25)' }}>
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <div style={{ fontSize: 42 }}>📊</div>
          <Title level={3} style={{ margin: 0 }}>DevStat</Title>
          <Text type="secondary">{mode === 'register' ? 'Create your account' : 'Sign in to your account'}</Text>
          <div style={{ marginTop: 8 }}>
            <Button type="link" style={{ padding: 0 }} onClick={() => setMode(mode === 'register' ? 'login' : 'register')}>
              {mode === 'register' ? 'Already have an account? Sign in' : 'New here? Create an account'}
            </Button>
          </div>
        </div>

        <Divider style={{ margin: '16px 0' }} />

        {!firebaseConfigured && (
          <Alert type="info" showIcon style={{ marginBottom: 16 }}
            message="Account setup needed"
            description="DevStat uses its own Firebase project. Add its config (API key, project id, app id) to VITE_FIREBASE_* to enable sign-up and sign-in." />
        )}

        <Tabs
          defaultActiveKey="email"
          centered
          items={[
            {
              key: 'email',
              label: <span><MailOutlined /> Email</span>,
              children: (
                <Form layout="vertical" onFinish={handleEmail} initialValues={{ email: '', password: '', confirmPassword: '' }}>
                  <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email', message: 'Valid email' }]}>
                    <Input prefix={<UserOutlined />} placeholder="you@example.com" />
                  </Form.Item>
                  {mode === 'register' && (
                    <Form.Item name="password" label="Password (min 8 chars)"
                      rules={[{ required: true, min: 8, message: 'Min 8 characters' }]}>
                      <Input.Password prefix={<LockOutlined />} placeholder="••••••••" />
                    </Form.Item>
                  )}
                  {mode === 'register' && (
                    <Form.Item
                      name="confirmPassword"
                      label="Confirm password"
                      dependencies={['password']}
                      hasFeedback
                      rules={[
                        { required: true, message: 'Please confirm your password' },
                        ({ getFieldValue }) => ({
                          validator(_, value) {
                            if (!value || getFieldValue('password') === value) {
                              return Promise.resolve();
                            }
                            return Promise.reject(new Error('Passwords do not match'));
                          },
                        }),
                      ]}>
                      <Input.Password prefix={<LockOutlined />} placeholder="••••••••" />
                    </Form.Item>
                  )}
                  {mode === 'login' && (
                    <Form.Item name="password" label="Password"
                      rules={[{ required: true, message: 'Enter your password' }]}>
                      <Input.Password prefix={<LockOutlined />} placeholder="••••••••" />
                    </Form.Item>
                  )}
                  <Button type="primary" htmlType="submit" loading={loading} block icon={mode === 'register' ? <UserOutlined /> : <LockOutlined />}>
                    {mode === 'register' ? 'Create account' : 'Sign in'}
                  </Button>
                  {mode === 'register' && (
                    <Button type="link" block style={{ marginTop: 4 }} onClick={() => setVerifyNotice(null)}>
                      Already have an account? Sign in
                    </Button>
                  )}
                </Form>
              ),
            },
            {
              key: 'google',
              label: <span><GoogleOutlined /> Google</span>,
              children: (
                <div style={{ textAlign: 'center', padding: '16px 0' }}>
                  <Button type="primary" size="large" icon={<GoogleOutlined />} loading={loading} onClick={handleGoogle} block>
                    Continue with Google
                  </Button>
                  <Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
                    No password needed. Your account is created automatically.
                  </Text>
                </div>
              ),
            },
          ]}
        />

        {verifyNotice && (
          <Alert type="warning" showIcon style={{ marginTop: 16 }} message="Verification required"
            description={<span>{verifyNotice}</span>} />
        )}

        {mode === 'register' && (
          <div style={{ marginTop: 12, fontSize: 12, color: '#8a97a6' }}>
            <CheckCircleOutlined /> {mode === 'register' ? 'Email registrations must verify their address (this keeps out bots).' : ''}
          </div>
        )}
      </Card>
    </div>
  )
}
