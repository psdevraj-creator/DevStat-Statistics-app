// DevStat Firebase configuration (its OWN project — separate from pubmed).
//
// To go live, create a Firebase project (e.g. "devstat-app") and paste its
// web-app config below (Project settings → Your apps → Web → Config), then
// enable Authentication: Email/Password, Google, and Phone in that project.
// The DATA here is yours to check in the Firebase console of that project.
import { initializeApp, type FirebaseApp } from 'firebase/app'
import { getAuth, type Auth } from 'firebase/auth'

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID ?? '',
}

/**
 * True once a real Firebase project config is present. Until then the login
 * page renders a friendly setup notice instead of failing silently.
 */
export const firebaseConfigured = Boolean(cfg.apiKey && cfg.projectId && cfg.appId)

let _app: FirebaseApp | null = null
let _auth: Auth | null = null

export function getFirebaseApp(): FirebaseApp {
  if (!_app) _app = initializeApp(cfg)
  return _app
}

export function getFirebaseAuth(): Auth {
  if (!_auth) _auth = getAuth(getFirebaseApp())
  return _auth
}
