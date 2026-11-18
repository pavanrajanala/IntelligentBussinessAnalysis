import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

const GREETING = {
  role: 'assistant',
  content:
    'Ask me about your sales data. I look up the real numbers before answering, and I can show you which steps I took.',
}

// Friendly names for the tools the agent can run (shown under "How I got this").
const TOOL_LABELS = {
  get_sales_trend: 'Sales trend',
  find_customer_switching: 'Customer switching',
  get_top_products: 'Product ranking',
  get_category_performance: 'Category performance',
  compare_periods: 'Month comparison',
  check_external_news: 'Web news search',
}

const GENERIC_SUGGESTIONS = [
  'Which category earns the most?',
  'Which are my lowest selling products?',
  'How did this month compare with last month?',
]

export default function ChatBot({ dataVersion, askRequest }) {
  const [messages, setMessages] = useState([GREETING])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState(GENERIC_SUGGESTIONS)
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const handledRequest = useRef(null)

  // Suggested questions: lead with the worst declining product, if there is one.
  useEffect(() => {
    let cancelled = false
    api('/api/dashboard/declining-products')
      .then((list) => {
        if (cancelled) return
        const first = list?.[0]?.product
        setSuggestions(first ? [`Why is ${first} declining?`, ...GENERIC_SUGGESTIONS] : GENERIC_SUGGESTIONS)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [dataVersion])

  // Keep the newest message in view by scrolling only the chat list (not the page).
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  const send = useCallback(
    async (text) => {
      const question = text.trim()
      if (!question || loading) return
      setMessages((m) => [...m, { role: 'user', content: question }])
      setInput('')
      setLoading(true)
      try {
        const data = await api('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question }),
        })
        setMessages((m) => [...m, { role: 'assistant', content: data.answer, trace: data.trace }])
      } catch (err) {
        setMessages((m) => [...m, { role: 'assistant', content: err.message, isError: true }])
      } finally {
        setLoading(false)
      }
    },
    [loading],
  )

  // A "Why?" button elsewhere on the page can ask the chatbot a question.
  useEffect(() => {
    if (askRequest && !loading && handledRequest.current !== askRequest.id) {
      handledRequest.current = askRequest.id
      send(askRequest.question)
    }
  }, [askRequest, loading, send])

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  function onInput(e) {
    setInput(e.target.value)
    const el = inputRef.current
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  const onlyGreeting = messages.length === 1

  return (
    <aside className="chat card" aria-label="Ask your data">
      <div className="chat__head">
        <h2 className="card__title">Ask your data</h2>
        <p className="card__subtitle">Plain-English questions, answered from your numbers</p>
      </div>

      <div className="chat__list" ref={listRef} role="log" aria-live="polite">
        {messages.map((m, i) => (
          <Message key={i} message={m} />
        ))}
        {loading && (
          <div className="msg msg--assistant">
            <div className="bubble bubble--assistant" aria-label="Assistant is thinking">
              <span className="dots">
                <span />
                <span />
                <span />
              </span>
            </div>
          </div>
        )}
      </div>

      {onlyGreeting && !loading && (
        <div className="chat__suggestions">
          {suggestions.map((s) => (
            <button key={s} className="chip" onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat__form"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <label htmlFor="chat-input" className="visually-hidden">
          Your question
        </label>
        <textarea
          id="chat-input"
          ref={inputRef}
          className="chat__input"
          value={input}
          onChange={onInput}
          onKeyDown={onKeyDown}
          placeholder="Ask a question…"
          rows={1}
        />
        <button className="btn btn--primary" type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </aside>
  )
}

function Message({ message }) {
  const isUser = message.role === 'user'
  const steps = message.trace ?? []

  return (
    <div className={`msg ${isUser ? 'msg--user' : 'msg--assistant'}`}>
      <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--assistant'} ${message.isError ? 'bubble--error' : ''}`}>
        {message.content}
        {steps.length > 0 && (
          <details className="trace">
            <summary>How I got this ({steps.length} step{steps.length > 1 ? 's' : ''})</summary>
            <ol>
              {steps.map((s, i) => (
                <li key={i}>
                  <span className="trace__tool">{TOOL_LABELS[s.tool] ?? s.tool}</span>
                  {Object.keys(s.arguments ?? {}).length > 0 && (
                    <span className="trace__args"> {Object.values(s.arguments).join(', ')}</span>
                  )}
                  {s.result?.error && <span className="trace__fail"> failed</span>}
                </li>
              ))}
            </ol>
          </details>
        )}
      </div>
    </div>
  )
}
