import { Line, Bar, Doughnut } from 'react-chartjs-2'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Tooltip, Filler } from 'chart.js'
import { inr, inrCompact, monthLabel } from '../format'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Tooltip, Filler)
ChartJS.defaults.font.family = "'Mukta', system-ui, sans-serif"
ChartJS.defaults.font.size = 13
ChartJS.defaults.color = '#6b645c'

const INK = '#e8731a'
const PALETTE = ['#f59e42', '#c9610f', '#ffd3a1', '#7a4a22', '#d8c3a8', '#a39484']
const grid = { color: '#f0e6da' }
const money = { callbacks: { label: (c) => ` ${inr(c.parsed.y ?? c.parsed.x ?? c.parsed)}` } }

export function RevenueLine({ trend }) {
  const data = {
    labels: trend.map((t) => monthLabel(t.month)),
    datasets: [{ data: trend.map((t) => t.revenue), borderColor: INK, backgroundColor: 'rgba(245,158,66,.16)', fill: true, tension: 0.25, pointRadius: 3, pointBackgroundColor: INK, borderWidth: 2 }],
  }
  const options = {
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: money },
    scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid, border: { display: false }, ticks: { callback: (v) => inrCompact(v) } } },
  }
  return <Line data={data} options={options} aria-label="Revenue by month" role="img" />
}

export function TopBar({ items }) {
  const data = { labels: items.map((i) => i.product), datasets: [{ data: items.map((i) => i.revenue), backgroundColor: '#f59e42', borderRadius: 4, barThickness: 16 }] }
  const options = {
    indexAxis: 'y',
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${inr(c.parsed.x)}` } } },
    scales: { x: { beginAtZero: true, grid, border: { display: false }, ticks: { callback: (v) => inrCompact(v) } }, y: { grid: { display: false } } },
  }
  return <Bar data={data} options={options} aria-label="Top products by revenue" role="img" />
}

export function CategoryRing({ items }) {
  const data = { labels: items.map((i) => i.category), datasets: [{ data: items.map((i) => i.revenue), backgroundColor: PALETTE, borderColor: '#fff', borderWidth: 2 }] }
  const options = {
    maintainAspectRatio: false,
    cutout: '62%',
    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } }, tooltip: { callbacks: { label: (c) => ` ${c.label}: ${inr(c.parsed)}` } } },
  }
  return <Doughnut data={data} options={options} aria-label="Revenue by category" role="img" />
}

export function CountLine({ rows, field }) {
  const data = {
    labels: rows.map((r) => r.date.slice(5)),
    datasets: [{ data: rows.map((r) => r[field]), borderColor: INK, backgroundColor: 'rgba(245,158,66,.16)', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2 }],
  }
  const options = {
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: { beginAtZero: true, grid, border: { display: false }, ticks: { precision: 0 } } },
  }
  return <Line data={data} options={options} role="img" aria-label={field} />
}
