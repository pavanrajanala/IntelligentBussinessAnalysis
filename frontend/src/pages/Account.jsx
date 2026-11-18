import { useState } from 'react'
import { put, post } from '../api'
import { useAuth } from '../auth'
import { useMeta } from '../components/useMeta'
import { Loading } from '../components/Empty'
import ShopFields from '../components/ShopFields'
import LocationFields from '../components/LocationFields'
import { navigate } from '../router'

export default function Account() {
  const { user, profile, refresh, signOut } = useAuth()
  const { meta, error: metaError } = useMeta()
  const [shop, setShop] = useState({ business_name: profile?.business_name ?? '', business_type: profile?.business_type ?? '', customer_mix: profile?.customer_mix ?? [] })
  const [loc, setLoc] = useState({ state: profile?.state ?? '', city: profile?.city ?? '', pincode: profile?.pincode ?? '', latitude: profile?.latitude ?? null, longitude: profile?.longitude ?? null })
  const [msg, setMsg] = useState({ ok: '', err: '' })
  const [busy, setBusy] = useState(false)
  const [del, setDel] = useState({ open: false, password: '', err: '' })

  async function save(e) {
    e.preventDefault()
    setMsg({ ok: '', err: '' })
    setBusy(true)
    try {
      await put('/api/profile', { ...shop, ...loc })
      await refresh()
      setMsg({ ok: 'Saved. Your order list and festival dates now use these details.', err: '' })
    } catch (err) {
      setMsg({ ok: '', err: err.message })
    } finally {
      setBusy(false)
    }
  }

  async function remove(e) {
    e.preventDefault()
    try {
      await post('/api/account/delete', { password: del.password })
      window.location.hash = '/login'
      window.location.reload()
    } catch (err) {
      setDel({ ...del, err: err.message })
    }
  }

  if (!meta) return metaError ? <p className="form-error">{metaError}</p> : <Loading />

  return (
    <>
      <header className="page-head">
        <h1>Account</h1>
        <p>{user.name} · {user.email}</p>
      </header>

      <form onSubmit={save} style={{ maxWidth: 560 }} noValidate>
        <section className="block">
          <div className="block__head"><h2>Your shop</h2></div>
          <ShopFields value={shop} onChange={setShop} meta={meta} />
        </section>
        <section className="block">
          <div className="block__head"><h2>Location</h2></div>
          <LocationFields value={loc} onChange={setLoc} states={meta.states} />
        </section>
        {msg.err && <p className="form-error" role="alert">{msg.err}</p>}
        {msg.ok && <p className="form-ok" role="status">{msg.ok}</p>}
        <div className="toolbar">
          <button className="btn btn--primary" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
          <button type="button" className="btn btn--quiet" onClick={signOut}>Sign out</button>
        </div>
      </form>

      <div className="danger-zone">
        <h2>Delete my account</h2>
        <p>This permanently removes your login, shop details, sales and saved questions. It cannot be undone.</p>
        {del.open ? (
          <form onSubmit={remove} style={{ maxWidth: 360 }}>
            <div className="field">
              <label htmlFor="del-pw">Type your password to confirm</label>
              <input id="del-pw" type="password" className="input" autoComplete="current-password" value={del.password} onChange={(e) => setDel({ ...del, password: e.target.value, err: '' })} />
            </div>
            {del.err && <p className="form-error" role="alert">{del.err}</p>}
            <div className="toolbar">
              <button className="btn btn--danger" disabled={!del.password}>Delete everything</button>
              <button type="button" className="btn btn--quiet" onClick={() => setDel({ open: false, password: '', err: '' })}>Cancel</button>
            </div>
          </form>
        ) : (
          <button className="btn btn--secondary" onClick={() => { setDel({ ...del, open: true }); navigate('/account') }}>Delete my account</button>
        )}
      </div>
    </>
  )
}
