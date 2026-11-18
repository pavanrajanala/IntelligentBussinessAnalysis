import { useApi } from '../components/useApi'
import { NoData, Loading, Problem } from '../components/Empty'
import { RevenueLine, TopBar, CategoryRing } from '../components/Charts'
import { useAuth } from '../auth'
import { Link, askAssistant } from '../router'
import { inr, number, monthLabel } from '../format'

export default function Overview() {
  const { user, profile } = useAuth()
  const o = useApi('/api/overview')
  const f = useApi('/api/forecast')

  if (o.loading) return <Loading />
  if (o.error) return <Problem message={o.error} onRetry={o.reload} />

  const first = user.name.split(' ')[0]
  if (!o.data.has_data) {
    return (
      <>
        <header className="page-head">
          <h1>Welcome, {first}</h1>
          <p>Let’s get {profile?.business_name || 'your shop'} set up.</p>
        </header>
        <NoData what="your overview" />
      </>
    )
  }

  const { kpi, trend, top, categories, declining } = o.data
  const g = kpi.growth_pct
  const fc = f.data?.found ? f.data : null
  const more = fc ? fc.products.filter((p) => p.action === 'Order more').slice(0, 4) : []

  return (
    <>
      <header className="page-head">
        <h1>{profile?.business_name || 'Overview'}</h1>
        <p>How {profile?.business_name ? 'the shop' : 'sales'} is doing, up to {monthLabel(kpi.latest_month)}.</p>
      </header>

      <dl className="figures">
        <div className="figure"><dt>Total sales</dt><dd>{inr(kpi.total_revenue)}</dd></div>
        <div className="figure"><dt>Bills</dt><dd>{number(kpi.total_orders)}</dd></div>
        <div className="figure"><dt>Average bill</dt><dd>{inr(kpi.avg_order_value)}</dd></div>
        <div className={`figure ${g >= 0 ? 'figure--up' : 'figure--down'}`}>
          <dt>Latest month</dt>
          <dd>{g >= 0 ? '+' : ''}{g}%</dd>
          <small>compared with the month before</small>
        </div>
      </dl>

      {fc && (
        <section className="block">
          <div className="block__head">
            <h2>{fc.target_label} at a glance</h2>
            <Link to="/orders">Full order list</Link>
          </div>
          {more.length ? (
            <p className="block__lead">
              Expect to sell about {inr(fc.total_forecast_revenue)}. Stock up most on{' '}
              {more.map((p, i) => (
                <span key={p.product}>{i > 0 && (i === more.length - 1 ? ' and ' : ', ')}<b>{p.product}</b> (order {number(p.suggested_order)})</span>
              ))}
              .
            </p>
          ) : (
            <p className="block__lead">Expect to sell about {inr(fc.total_forecast_revenue)}. Nothing needs a big increase; the full list has the quantities.</p>
          )}
        </section>
      )}

      <section className="block">
        <div className="block__head"><h2>Sales by month</h2></div>
        <div className="chart"><RevenueLine trend={trend} /></div>
      </section>

      <div className="two-col">
        <section className="block">
          <div className="block__head"><h2>Best sellers</h2></div>
          <div className="chart"><TopBar items={top} /></div>
        </section>
        <section className="block">
          <div className="block__head"><h2>Sales by category</h2></div>
          <div className="chart"><CategoryRing items={categories} /></div>
        </section>
      </div>

      {declining.length > 0 && (
        <section className="block">
          <div className="block__head"><h2>Products to watch</h2></div>
          <p className="block__lead">These sold noticeably less lately than when you started.</p>
          <ul className="watch">
            {declining.map((d) => (
              <li key={d.product}>
                <span className="name">{d.product}</span>
                <span className="range">{inr(d.first_month_revenue)} to {inr(d.latest_month_revenue)} a month</span>
                <span className="pct">{d.pct_change}%</span>
                <button className="link-button" onClick={() => askAssistant(`Why are ${d.product} sales going down, and who stopped buying it?`)}>Ask why</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
