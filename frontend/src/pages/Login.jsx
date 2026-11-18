import { useState } from 'react'
import { post } from '../api'
import { useAuth } from '../auth'
import { Link, navigate } from '../router'
import { Wordmark } from '../components/Brand'

export default function Login({ notice }) {
  const { refresh } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!form.email.trim() || !form.password) {
      setError('Enter your email and password.')
      return
    }
    setBusy(true)
    try {
      await post('/api/auth/login', { email: form.email.trim(), password: form.password })
      if (await refresh()) navigate('/')
      else setError('Signed in, but your browser did not keep the sign-in cookie, so the next request was refused. Open the app at the address the server prints (for example http://localhost:5173 in development) and make sure cookies are not blocked for it. If you set COOKIE_SECURE=true, it only works over https.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="entry">
      <Wordmark href="#/login" />
      <div className="entry__form-wrap">
        <form className="entry__form" onSubmit={submit} noValidate>
          <h2>Sign in</h2>
          <p>Welcome back. Your sales and past questions are saved to your account.</p>
          {(error || notice) && <p className="form-error" role="alert">{error || notice}</p>}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" className="input" type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <button className="btn btn--primary" style={{ width: '100%' }} disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="entry__switch">
            New here? <Link to="/signup">Create an account</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
