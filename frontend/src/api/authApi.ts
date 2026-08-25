import { accountApi, getToken } from '../api/client'
import { useAuth } from '../stores/authStore'

// A stable per-device id used for the concurrent-session/device guard.
export function getDeviceId(): string {
  const KEY = 'devstat_device_id'
  try {
    let id = localStorage.getItem(KEY)
    if (!id) {
      id = (globalThis.crypto?.randomUUID?.() ?? `d-${Date.now()}-${Math.random().toString(16).slice(2)}`)
      localStorage.setItem(KEY, id)
    }
    return id
  } catch {
    return `d-${Date.now()}`
  }
}

export const authApi = {
  // Create a DevStat session with a Firebase ID token + this device's id.
  session: async (idToken: string) => {
    const res = await accountApi.post('/api/auth/session', { id_token: idToken, device_id: getDeviceId() })
    return res.data
  },
  me: async () => {
    const res = await accountApi.get('/api/auth/me', {
      headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
    })
    return res.data
  },
  logout: async () => {
    try {
      await accountApi.post('/api/auth/logout', {})
    } catch {
      // ignore
    }
  },
  status: async () => {
    const res = await accountApi.get('/api/license/status', {
      headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
    })
    return res.data
  },
  use: async () => {
    const res = await accountApi.post('/api/license/use', {}, {
      headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
    })
    return res.data
  },
  checkout: async () => {
    const res = await accountApi.post('/api/license/checkout', {}, {
      headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
    })
    return res.data
  },
}

// Persist the DevStat session (signed session token, not the raw Firebase token).
export function storeDevStatSession(session: any) {
  useAuth.getState().setSession(
    {
      uid: session.uid ?? '',
      email: session.email ?? undefined,
      name: session.name ?? undefined,
      provider: session.provider ?? 'email',
      verified: Boolean(session.verified),
      plan: session.plan ?? 'free',
      licensed: Boolean(session.licensed),
      licensed_until: session.licensed_until ?? null,
    },
    session.session_token ?? '',
  )
}

