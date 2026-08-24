// DevStat in-app auth state (persisted to localStorage).
import { create } from 'zustand'

export interface SessionUser {
  uid: string
  email?: string
  name?: string
  provider: 'google' | 'email' | 'phone'
  verified: boolean
  plan?: string        // 'free' | 'pro'
  licensed?: boolean   // true when a paid (£25/yr) licence is active
  usageCount?: number
  licensed_until?: string | null
}

interface AuthState {
  user: SessionUser | null
  token: string | null
  setSession: (user: SessionUser, token: string) => void
  clearSession: () => void
}

const KEY = 'devstat_session'

function load(): { user: SessionUser | null; token: string | null } {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : { user: null, token: null }
  } catch {
    return { user: null, token: null }
  }
}

const initial = load()

export const useAuth = create<AuthState>((set) => ({
  user: initial.user,
  token: initial.token,
  setSession: (user, token) => {
    localStorage.setItem(KEY, JSON.stringify({ user, token }))
    set({ user, token })
  },
  clearSession: () => {
    localStorage.removeItem(KEY)
    set({ user: null, token: null })
  },
}))
