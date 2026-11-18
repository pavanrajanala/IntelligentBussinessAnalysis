import { useState } from 'react'
import { patch } from '../api'
import { useApi } from '../components/useApi'
import { Loading, Problem } from '../components/Empty'
import { CountLine } from '../components/Charts'
import { useAuth } from '../auth'
import { useMeta } from '../components/useMeta'
import { number, dateLabel, when } from '../format'

function Bars({ rows, empty }) {
  if (!rows.length) return <p className="muted">{empty}</p>
  const max = Math.max(...rows.map((r) => r.count), 1)
  return (
    <ul className="bars">
      {rows.map((r) => (
        <li key={r.label}>
          <span>{r.label}</span>
          <span className="n">{number(r.count)}</span>
          <span className="track"><span style={{ width: `${(r.count / max) * 100}%` }} /></span>
        </li>
      ))}
    </ul>
  )
}

export default function Admin() {
  const { user } = useAuth()
  const { meta } = useMeta()
  const stats = useApi('/api/admin/stats')
  const [q, setQ] = useState('')
  const [applied, setApplied] = useState('')
  const users = useApi(`/api/admin/users?q=${encodeURIComponent(applied)}`)
  const [err, setErr] = useState('')

  async function toggle(u) {
    setErr('')
    try {
      await patch(`/api/admin/users/${u.id}`, { is_active: !u.is_active })
      users.reload()
      stats.reload()
    } catch (e) {
      setErr(e.message)
    }
  }

  if (stats.loading) return <Loading />
  if (stats.error) return <Problem message={stats.error} onRetry={stats.reload} />
  const t = stats.data.totals

  return (
    <>
      <header className="page-head">
        <h1>Admin</h1>
        <p>Who is using Intelligent Business Analyst. You see account details and usage counts only, never anyone’s sales or chat text.</p>
      </header>

      <dl className="figures">
        <div className="figure"><dt>Customers</dt><dd>{number(t.customers)}</dd><small>{t.new_7_days} joined this week</small></div>
        <div className="figure"><dt>Active this month</dt><dd>{number(t.active_30_days)}</dd><small>{t.active_7_days} in the last 7 days</small></div>
        <div className="figure"><dt>With sales data</dt><dd>{number(t.customers_with_data)}</dd><small>{number(t.sales_rows)} rows in total</small></div>
        <div className="figure"><dt>Questions asked</dt><dd>{number(t.questions_asked)}</dd><small>{t.questions_7_days} this week · {t.news_searches} used web news</small></div>
      </dl>

      <div className="two-col">
        <section className="block">
          <div className="block__head"><h2>New customers, last 30 days</h2></div>
          <div className="chart chart--short"><CountLine rows={stats.data.signups_per_day} field="signups" /></div>
        </section>
        <section className="block">
          <div className="block__head"><h2>Questions, last 30 days</h2></div>
          <div className="chart chart--short"><CountLine rows={stats.data.questions_per_day} field="questions" /></div>
        </section>
      </div>

      <div className="two-col">
        <section className="block"><div className="block__head"><h2>Kinds of shop</h2></div><Bars rows={stats.data.business_types} empty="No customers yet." /></section>
        <section className="block"><div className="block__head"><h2>States</h2></div><Bars rows={stats.data.states} empty="No locations yet." /></section>
      </div>
      <section className="block"><div className="block__head"><h2>Who shops with them</h2></div><Bars rows={stats.data.customer_mix.map((r) => ({ ...r, label: meta?.customer_types.find((c) => c.id === r.label)?.label ?? r.label }))} empty="No answers yet." /></section>

      <section className="block">
        <div className="block__head"><h2>Customers</h2></div>
        <form className="toolbar" onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()) }}>
          <label htmlFor="user-search" className="visually-hidden">Search customers</label>
          <input id="user-search" className="input" style={{ maxWidth: 320 }} placeholder="Search by name, email or shop" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn btn--secondary btn--small">Search</button>
        </form>
        {err && <p className="form-error" role="alert">{err}</p>}
        {users.error && <Problem message={users.error} onRetry={users.reload} />}
        <div className="ledger-wrap">
          <table className="ledger">
            <thead>
              <tr><th className="left">Customer</th><th className="left">Shop</th><th className="left">Where</th><th className="left">Joined</th><th className="left">Last seen</th><th>Rows</th><th>Questions</th><th className="left">Status</th></tr>
            </thead>
            <tbody>
              {(users.data ?? []).map((u) => (
                <tr key={u.id}>
                  <td className="left item">{u.name}{u.role === 'admin' ? ' (admin)' : ''}<small>{u.email}</small></td>
                  <td className="left">{u.business_name || '—'}<small className="muted" style={{ display: 'block' }}>{u.business_type}</small></td>
                  <td className="left">{[u.city, u.state].filter(Boolean).join(', ') || '—'}</td>
                  <td className="left">{dateLabel(u.created_at)}</td>
                  <td className="left">{when(u.last_login_at)}</td>
                  <td>{number(u.sales_rows)}</td>
                  <td>{number(u.questions)}</td>
                  <td className="left">
                    <span className={`status ${u.is_active ? 'status--on' : 'status--off'}`}>{u.is_active ? 'Active' : 'Suspended'}</span>
                    {u.id !== user.id && <> <button className="link-button" onClick={() => toggle(u)}>{u.is_active ? 'Suspend' : 'Reactivate'}</button></>}
                  </td>
                </tr>
              ))}
              {users.data?.length === 0 && <tr><td colSpan={8} className="left muted">No customers match.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
