import { useEffect, useState } from 'react'
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { api } from './api'
import { inr, inrCompact, monthLabel, number } from './format'

ChartJS.register(ArcElement, BarElement, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip)

// Chart colours come from one place so every chart matches the page.
const COLORS = {
  primary: '#1d6b57',
  primarySoft: 'rgba(29, 107, 87, 0.10)',
  blue: '#2f6fa3',
  text: '#667085',
  grid: '#eceff3',
  series: ['#1d6b57', '#2f6fa3', '#c2410c', '#7c5cbf', '#b08900', '#64748b'],
}
ChartJS.defaults.font.family = "'IBM Plex Sans', system-ui, sans-serif"
ChartJS.defaults.font.size = 12
ChartJS.defaults.color = COLORS.text

const tooltip = {
  backgroundColor: '#1b2330',
  padding: 10,
  cornerRadius: 6,
  displayColors: false,
}

const moneyAxis = {
  beginAtZero: true,
  grid: { color: COLORS.grid },
  border: { display: false },
  ticks: { callback: (v) => inrCompact(v) },
}

const lineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: { ...tooltip, callbacks: { label: (c) => inr(c.parsed.y) } },
  },
  scales: { x: { grid: { display: false }, border: { color: COLORS.grid } }, y: moneyAxis },
}

const barOptions = {
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { ...tooltip, callbacks: { label: (c) => inr(c.parsed.x) } },
  },
  scales: {
    x: { ...moneyAxis },
    y: { grid: { display: false }, border: { display: false } },
  },
}

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '62%',
  plugins: {
    legend: { position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, padding: 14, usePointStyle: true } },
    tooltip: {
      ...tooltip,
      callbacks: {
        label: (c) => {
          const total = c.dataset.data.reduce((a, b) => a + b, 0)
          return `${c.label}: ${inr(c.parsed)} (${((c.parsed / total) * 100).toFixed(1)}%)`
        },
      },
    },
  },
}

export default function Dashboard({ onAsk }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const [tick, setTick] = useState(0) // bump to retry after an error

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api('/api/dashboard/kpi-summary'),
      api('/api/dashboard/revenue-trend'),
      api('/api/dashboard/top-products?n=6'),
      api('/api/dashboard/category-breakdown'),
      api('/api/dashboard/declining-products'),
    ])
      .then(([kpi, trend, top, categories, declining]) => {
        if (cancelled) return
        setData({ kpi, trend, top, categories, declining })
        setError('')
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [tick])

  if (error) {
    return (
      <div className="dashboard">
        <div className="notice notice--error" role="alert">
          <p>{error}</p>
          <button
            className="btn btn--secondary"
            onClick={() => {
              setError('')
              setTick((t) => t + 1)
            }}
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-label="Loading dashboard">
        <div className="kpi-row">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton skeleton--kpi" />
          ))}
        </div>
        <div className="skeleton skeleton--chart" />
      </div>
    )
  }

  const { kpi, trend, top, categories, declining } = data
  const growth = kpi.growth_pct

  return (
    <div className="dashboard">
      <div className="kpi-row">
        <Kpi label="Total revenue" value={inr(kpi.total_revenue)} hint="Excludes flagged outliers" />
        <Kpi label="Orders" value={number(kpi.total_orders)} hint="Cleaned order lines" />
        <Kpi label="Average order value" value={inr(kpi.avg_order_value)} hint="Revenue per order line" />
        <Kpi
          label="Revenue growth"
          value={growth === null ? '—' : `${growth > 0 ? '+' : ''}${growth}%`}
          tone={growth === null ? 'neutral' : growth >= 0 ? 'positive' : 'negative'}
          hint={kpi.latest_month ? `${monthLabel(kpi.latest_month)} vs previous month` : 'Needs two months of data'}
        />
      </div>

      <Card title="Revenue over time" subtitle="Total revenue per month">
        <div className="chart chart--line">
          <Line
            data={{
              labels: trend.map((r) => monthLabel(r.month)),
              datasets: [
                {
                  data: trend.map((r) => r.revenue),
                  borderColor: COLORS.primary,
                  backgroundColor: COLORS.primarySoft,
                  borderWidth: 2,
                  pointRadius: 3,
                  pointBackgroundColor: COLORS.primary,
                  tension: 0.3,
                  fill: true,
                },
              ],
            }}
            options={lineOptions}
          />
        </div>
      </Card>

      <div className="grid-2">
        <Card title="Top products" subtitle="By revenue">
          <div className="chart chart--bar">
            <Bar
              data={{
                labels: top.map((p) => p.product),
                datasets: [{ data: top.map((p) => p.revenue), backgroundColor: COLORS.blue, borderRadius: 3, barThickness: 18 }],
              }}
              options={barOptions}
            />
          </div>
        </Card>

        <Card title="Revenue by category" subtitle="Share of total revenue">
          <div className="chart chart--bar">
            <Doughnut
              data={{
                labels: categories.map((c) => c.category),
                datasets: [
                  {
                    data: categories.map((c) => c.revenue),
                    backgroundColor: categories.map((_, i) => COLORS.series[i % COLORS.series.length]),
                    borderColor: '#ffffff',
                    borderWidth: 2,
                  },
                ],
              }}
              options={doughnutOptions}
            />
          </div>
        </Card>
      </div>

      <Card
        title="Products to watch"
        subtitle="Revenue in their latest month is more than 15% below their first month"
        tone="alert"
      >
        {declining.length === 0 ? (
          <p className="empty">No products are declining by more than 15%.</p>
        ) : (
          <ul className="decline">
            {declining.map((d) => (
              <li key={d.product} className="decline__row">
                <div className="decline__name">{d.product}</div>
                <div className="decline__range">
                  {inrCompact(d.first_month_revenue)} <span aria-hidden="true">→</span>
                  <span className="visually-hidden"> to </span> {inrCompact(d.latest_month_revenue)}
                </div>
                <div className="decline__pct">{d.pct_change}%</div>
                <button className="btn btn--small btn--secondary" onClick={() => onAsk(`Why is ${d.product} declining?`)}>
                  Ask why
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function Card({ title, subtitle, tone, children }) {
  return (
    <section className={`card ${tone === 'alert' ? 'card--alert' : ''}`}>
      <h2 className="card__title">{title}</h2>
      {subtitle && <p className="card__subtitle">{subtitle}</p>}
      {children}
    </section>
  )
}

function Kpi({ label, value, hint, tone = 'neutral' }) {
  return (
    <div className={`kpi kpi--${tone}`}>
      <div className="kpi__label">{label}</div>
      <div className="kpi__value">{value}</div>
      <div className="kpi__hint">{hint}</div>
    </div>
  )
}
