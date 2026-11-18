import { useApi } from '../components/useApi'
import { Loading, Problem } from '../components/Empty'
import { Link, askAssistant } from '../router'
import { dayMonth } from '../format'

export default function Season() {
  const { data, error, loading, reload } = useApi('/api/outlook')
  if (loading) return <Loading />
  if (error) return <Problem message={error} onRetry={reload} />

  const { season, next_month_season: next, upcoming, tips, state } = data
  const changes = next && next.name !== season.name

  return (
    <>
      <header className="page-head">
        <h1>Season and festivals</h1>
        <p>{state ? `What is coming up in ${state}.` : 'What is coming up near you.'} {!state && <Link to="/account">Add your state</Link>}</p>
      </header>

      <div className="season-line">
        <div>
          <span className="label">Right now</span>
          <h3>{season.name}</h3>
          <p>{season.note}</p>
        </div>
        {changes && (
          <div>
            <span className="label">Next month</span>
            <h3>{next.name}</h3>
            <p>{next.note}</p>
          </div>
        )}
      </div>

      <section className="block">
        <div className="block__head"><h2>Festivals in the next few weeks</h2></div>
        {upcoming.length === 0 && <p className="muted">No major festivals in the next 75 days.</p>}
        {upcoming.map((f) => (
          <article className="festival" key={f.name + f.date}>
            <div className="festival__date">
              <b>{dayMonth(f.date).split(' ')[0]}</b>
              <span>{dayMonth(f.date).split(' ')[1]}</span>
            </div>
            <div>
              <div className="festival__name">
                <h3>{f.name}</h3>
                <span className="festival__when">{f.days_away === 0 ? 'today' : `in ${f.days_away} days`}{f.approx ? ' (date approximate, depends on the moon)' : ''}</span>
              </div>
              <span className="festival__stock">
                {f.stock_now ? 'Start stocking now' : `Stock up by ${dayMonth(f.stock_by)}`}
              </span>
              <p className="note">{f.note}</p>
              <ul className="festival__items">
                {f.items.map((it) => (
                  <li key={it.group}>
                    <b>{it.group}</b> <span className="plus">+{it.boost_pct}%</span>
                    {it.your_products.length > 0 && <> · you sell {it.your_products.join(', ')}</>}
                    {it.ideas.length > 0 && <span className="muted"> · also consider {it.ideas.join(', ')}</span>}
                  </li>
                ))}
                {f.other_ideas?.length > 0 && <li className="muted">Other ideas: {f.other_ideas.join(', ')}</li>}
              </ul>
              <button className="link-button" style={{ marginTop: 10 }} onClick={() => askAssistant(`How much extra should I stock for ${f.name}?`)}>Ask how much</button>
            </div>
          </article>
        ))}
      </section>

      {tips?.length > 0 && (
        <section className="block">
          <div className="block__head"><h2>For your kind of shop</h2></div>
          <ul className="tips">{tips.map((t) => <li key={t}>{t}</li>)}</ul>
        </section>
      )}
    </>
  )
}
