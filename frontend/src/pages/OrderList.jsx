import { useMemo, useState } from 'react'
import { useApi } from '../components/useApi'
import { NoData, Loading, Problem } from '../components/Empty'
import { useAuth } from '../auth'
import { inr, number, plural } from '../format'

const TAG = { 'Order more': 'more', 'Order less': 'less', 'Keep the same': 'same' }

function loadStock(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || '{}')
  } catch {
    return {}
  }
}

export default function OrderList() {
  const { user, profile } = useAuth()
  const { data, error, loading, reload } = useApi('/api/forecast')
  const [tab, setTab] = useState('all')
  const [note, setNote] = useState('')
  const key = `dd-stock-${user.id}-${data?.target_month ?? ''}`
  const [stock, setStock] = useState(() => loadStock(key))
  const [loadedKey, setLoadedKey] = useState(key)
  if (loadedKey !== key) {
    setLoadedKey(key)
    setStock(loadStock(key))
  }

  const rows = useMemo(() => {
    if (!data?.found) return []
    const all = data.products.map((p) => {
      const have = Number(stock[p.product] || 0)
      return { ...p, have, toBuy: Math.max(0, p.suggested_order - have) }
    })
    if (tab === 'more') return all.filter((r) => r.action === 'Order more')
    if (tab === 'less') return all.filter((r) => r.action === 'Order less')
    return all
  }, [data, stock, tab])

  if (loading) return <Loading />
  if (error) return <Problem message={error} onRetry={reload} />
  if (!data.found) {
    return (
      <>
        <header className="page-head"><h1>Order list</h1></header>
        {data.message ? <div className="notice">{data.message}</div> : null}
        <NoData what="your order list" />
      </>
    )
  }

  function setHave(product, value) {
    const next = { ...stock, [product]: value.replace(/\D/g, '') }
    setStock(next)
    try {
      localStorage.setItem(key, JSON.stringify(next))
    } catch {
      /* storage unavailable: the numbers just last for this visit */
    }
  }

  const counts = {
    more: data.products.filter((p) => p.action === 'Order more').length,
    less: data.products.filter((p) => p.action === 'Order less').length,
  }

  const asText = () =>
    [`Order list for ${data.target_label}${profile?.business_name ? ` (${profile.business_name})` : ''}`, '']
      .concat(rows.filter((r) => r.toBuy > 0).map((r) => `${r.product}: ${number(r.toBuy)}`))
      .join('\n')

  async function copy() {
    try {
      await navigator.clipboard.writeText(asText())
      setNote('Copied. Paste it into a message.')
    } catch {
      setNote('Could not copy. Use Print instead.')
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>Order list for {data.target_label}</h1>
        <p>{data.season?.name ? `${data.season.name}. ` : ''}Built from your last {data.based_on_months} months of sales.</p>
      </header>

      {data.warnings?.map((w) => <div className="notice" key={w}>{w}</div>)}

      <dl className="order-summary">
        <div><dt>Expected sales</dt><dd>{inr(data.total_forecast_revenue)}</dd></div>
        <div><dt>Order more</dt><dd>{plural(counts.more, 'item')}</dd></div>
        <div><dt>Order less</dt><dd>{plural(counts.less, 'item')}</dd></div>
      </dl>

      <div className="toolbar">
        <div className="tabs" role="group" aria-label="Filter the list">
          {[['all', 'All items'], ['more', 'Order more'], ['less', 'Order less']].map(([id, label]) => (
            <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn btn--secondary btn--small" onClick={copy}>Copy as text</button>
        <a className="btn btn--secondary btn--small" target="_blank" rel="noreferrer" href={`https://wa.me/?text=${encodeURIComponent(asText())}`}>Send on WhatsApp</a>
        <button className="btn btn--secondary btn--small" onClick={() => window.print()}>Print</button>
      </div>
      <p className="muted small" role="status" style={{ minHeight: '1.4em' }}>{note || 'Type what you already have in stock and the quantity to buy updates.'}</p>

      <div className="ledger-wrap">
        <table className="ledger ledger--stack">
          <caption className="visually-hidden">Suggested order quantities for {data.target_label}</caption>
          <thead>
            <tr>
              <th scope="col" className="left">Item</th>
              <th scope="col">Last month</th>
              <th scope="col">Expected</th>
              <th scope="col">In stock</th>
              <th scope="col">Order</th>
              <th scope="col" className="left">Why</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.product}>
                <td className="left item">
                  {r.product}
                  <small>{r.category} · <span className={`tag tag--${TAG[r.action]}`}>{r.action}</span></small>
                </td>
                <td data-label="Last month">{number(r.last_month_units)}</td>
                <td data-label="Expected">{number(r.forecast_units)}</td>
                <td data-label="In stock">
                  <input className="stock-input" inputMode="numeric" aria-label={`${r.product} already in stock`} value={stock[r.product] ?? ''} placeholder="0" onChange={(e) => setHave(r.product, e.target.value)} />
                </td>
                <td className="order-cell" data-label="Order">{number(r.toBuy)}</td>
                <td className="left why">
                  <ul>{r.why.map((w) => <li key={w}>{w}</li>)}</ul>
                  <small className="muted">{r.confidence} confidence</small>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6} className="left muted">Nothing in this group.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ marginTop: 16, maxWidth: '46em' }}>
        This is a careful estimate from your own sales, the season and festivals, with a small safety buffer. It cannot know about a new shop opening nearby or a supplier running out, so use your judgement.
      </p>
    </>
  )
}
