import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, post } from './api'

const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }) {
  const [state, setState] = useState({ loading: true, user: null, profile: null, summary: null, error: '' })

  const refresh = useCallback(async () => {
    try {
      const me = await api('/api/auth/me')
      setState({ loading: false, user: me.user, profile: me.profile, summary: me.summary, error: '' })
      return true
    } catch (err) {
      // 401 just means "not signed in"; anything else is a real problem worth showing.
      const signedOut = /sign in/i.test(err.message)
      setState({ loading: false, user: null, profile: null, summary: null, error: signedOut ? '' : err.message })
      return false
    }
  }, [])

  useEffect(() => {
    // Initial session check; the setState happens after the request resolves, not synchronously.
    api('/api/auth/me')
      .then((me) => setState({ loading: false, user: me.user, profile: me.profile, summary: me.summary, error: '' }))
      .catch((err) => setState({ loading: false, user: null, profile: null, summary: null, error: /sign in/i.test(err.message) ? '' : err.message }))
    const onExpired = () => setState((s) => ({ ...s, user: null, profile: null, summary: null, loading: false }))
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  const signOut = useCallback(async () => {
    try {
      await post('/api/auth/logout', {})
    } finally {
      setState({ loading: false, user: null, profile: null, summary: null, error: '' })
      window.location.hash = '/login'
    }
  }, [])

  const value = useMemo(() => ({ ...state, refresh, signOut }), [state, refresh, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
