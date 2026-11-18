import { useState } from 'react'
import { post } from '../api'
import { useAuth } from '../auth'
import { Link } from '../router'
import { Wordmark } from '../components/Brand'
import { useMeta } from '../components/useMeta'
import ShopFields from '../components/ShopFields'
import LocationFields from '../components/LocationFields'

const TITLES = ['Create your account', 'About your shop', 'Where is your shop?']
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function Signup() {
  const { refresh } = useAuth()
  const { meta, error: metaError } = useMeta()
  const [step, setStep] = useState(0)
  const [account, setAccount] = useState({ name: '', email: '', password: '' })
  const [shop, setShop] = useState({ business_name: '', business_type: '', customer_mix: [] })
  const [loc, setLoc] = useState({ state: '', city: '', pincode: '', latitude: null, longitude: null })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function check() {
    if (step === 0) {
      if (!account.name.trim()) return 'Please enter your name.'
      if (!EMAIL.test(account.email.trim())) return 'Please enter a valid email address.'
      if (account.password.length < 8) return 'Choose a password of at least 8 characters.'
    }
    if (step === 1) {
      if (!shop.business_name.trim()) return 'Please enter your shop name.'
      if (!shop.business_type) return 'Please choose the kind of shop.'
    }
    if (step === 2 && !loc.state) return 'Please choose your state, or use your current location.'
    return ''
  }

  async function next(e) {
    e.preventDefault()
    const problem = check()
    setError(problem)
    if (problem) return
    if (step < 2) {
      setStep(step + 1)
      return
    }
    setBusy(true)
    try {
      await post('/api/auth/signup', {
        name: account.name.trim(),
        email: account.email.trim(),
        password: account.password,
        ...shop,
        business_name: shop.business_name.trim(),
        ...loc,
        city: loc.city.trim(),
      })
      if (!(await refresh())) setError('Signed in, but your browser did not keep the sign-in cookie, so the next request was refused. Open the app at the address the server prints (for example http://localhost:5173 in development) and make sure cookies are not blocked for it. If you set COOKIE_SECURE=true, it only works over https.')
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
        <form className="entry__form" onSubmit={next} noValidate>
          <div className="steps">
            <span>Step {step + 1} of 3</span>
          </div>
          <div className="steps__bar"><span style={{ width: `${((step + 1) / 3) * 100}%` }} /></div>
          <h2>{TITLES[step]}</h2>
          {(error || metaError) && <p className="form-error" role="alert">{error || metaError}</p>}

          {step === 0 && (
            <>
              <div className="field">
                <label htmlFor="name">Your name</label>
                <input id="name" className="input" autoComplete="name" value={account.name} onChange={(e) => setAccount({ ...account, name: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" className="input" type="email" autoComplete="email" value={account.email} onChange={(e) => setAccount({ ...account, email: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="password">Password</label>
                <input id="password" className="input" type="password" autoComplete="new-password" value={account.password} onChange={(e) => setAccount({ ...account, password: e.target.value })} />
                <p className="hint">At least 8 characters.</p>
              </div>
            </>
          )}
          {step === 1 && meta && <ShopFields value={shop} onChange={setShop} meta={meta} />}
          {step === 2 && meta && <LocationFields value={loc} onChange={setLoc} states={meta.states} />}
          {step > 0 && !meta && !metaError && <p className="muted">Loading…</p>}

          <div className="toolbar" style={{ marginTop: 8 }}>
            <button className="btn btn--primary" disabled={busy || (step > 0 && !meta)}>
              {step < 2 ? 'Continue' : busy ? 'Creating account…' : 'Create account'}
            </button>
            {step > 0 && (
              <button type="button" className="btn btn--quiet" onClick={() => { setError(''); setStep(step - 1) }}>
                Back
              </button>
            )}
          </div>
          <p className="entry__switch">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
