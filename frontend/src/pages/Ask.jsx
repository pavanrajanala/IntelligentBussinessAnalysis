import { useEffect, useRef, useState } from 'react'
import { api, post } from '../api'
import { takePendingQuestion } from '../router'
import { NoData, Loading } from '../components/Empty'
import { useAuth } from '../auth'

const SUGGESTIONS = [
  'What should I order more of next month?',
  'Which festival should I prepare for first?',
  'Which products are selling less than before?',
  'Which customers stopped buying?',
]

const stepName = { get_sales_trend: 'Looked at monthly sales', find_customer_switching: 'Checked customers who stopped buying', get_top_products: 'Ranked your best sellers', get_category_performance: 'Compared categories', compare_periods: 'Compared two periods', forecast_next_month: 'Worked out next month’s order list', festival_outlook: 'Checked the season and festivals', check_external_news: 'Searched recent web news' }

export default function Ask() {
  const { summary } = useAuth()
  const [turns, setTurns] = useState(null)
  const [text, setText] = useState('')
  const [news, setNews] = useState(false)
  const [busy, setBusy] = useState(false)
  const bottom = useRef(null)
  const started = useRef(false)

  async function send(question) {
    const q = question.trim()
    if (!q || busy) return
    setText('')
    setBusy(true)
    setTurns((t) => [...(t ?? []), { q, a: null }])
    try {
      const r = await post('/api/chat', { question: q, use_news: news })
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { q, a: r.answer, sources: r.sources, trace: r.trace } : x)))
    } catch (err) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { q, a: err.message, error: true } : x)))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (started.current) return
    started.current = true
    api('/api/chat/history')
      .then((rows) => {
        const out = []
        for (const m of rows) {
          if (m.role === 'user') out.push({ q: m.content, a: null })
          else if (out.length) Object.assign(out[out.length - 1], { a: m.content, sources: m.trace?.sources, trace: m.trace?.trace })
        }
        setTurns(out)
        const pending = takePendingQuestion()
        if (pending) send(pending)
      })
      .catch(() => setTurns([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [turns])

  async function clear() {
    await api('/api/chat/history', { method: 'DELETE' })
    setTurns([])
  }

  if (!summary?.has_data) {
    return (
      <>
        <header className="page-head"><h1>Ask</h1></header>
        <NoData what="the assistant" />
      </>
    )
  }
  if (turns === null) return <Loading />

  return (
    <div className="ask">
      <header className="page-head page-head__row">
        <div>
          <h1>Ask about your shop</h1>
          <p>Plain questions, answered from your own sales. Amounts are always in rupees.</p>
        </div>
        {turns.length > 0 && <button className="btn btn--quiet btn--small" onClick={clear}>Clear chat</button>}
      </header>

      <div className="ask__log" aria-live="polite">
        {turns.length === 0 && (
          <div className="ask__suggest">
            {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
          </div>
        )}
        {turns.map((t, i) => (
          <div className="turn" key={i}>
            <div className="turn__q">{t.q}</div>
            {t.a === null ? (
              <span className="dots" role="status" aria-label="Working on it"><span /><span /><span /></span>
            ) : (
              <div className={`turn__a ${t.error ? 'turn__a--error' : ''}`}>{t.a}</div>
            )}
            {t.sources?.length > 0 && (
              <div className="turn__meta">
                Sources
                <ul>{t.sources.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title || s.url}</a></li>)}</ul>
              </div>
            )}
            {t.trace?.length > 0 && (
              <div className="turn__meta">
                <details>
                  <summary>How I got this</summary>
                  <ol>{t.trace.map((s, k) => <li key={k}>{stepName[s.tool] ?? s.tool}</li>)}</ol>
                </details>
              </div>
            )}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text) }}>
        <div className="composer__row">
          <label htmlFor="q" className="visually-hidden">Your question</label>
          <textarea id="q" rows={1} value={text} placeholder="Ask anything about your sales…" onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text) } }} />
          <button className="btn btn--primary" disabled={busy || !text.trim()}>Ask</button>
        </div>
        <div className="composer__opts">
          <label className="check">
            <input type="checkbox" checked={news} onChange={(e) => setNews(e.target.checked)} />
            Include recent web news
          </label>
          <span className="muted">Off by default, so answers come from your own data.</span>
        </div>
      </form>
    </div>
  )
}
