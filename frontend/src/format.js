// Number and date formatting helpers (Indian rupees, lakh/crore style).

export function inr(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—'
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

// Short form for chart axes: ₹12k, ₹1.5L, ₹2.3Cr
export function inrCompact(n) {
  const v = Number(n)
  if (Number.isNaN(v)) return ''
  const abs = Math.abs(v)
  const trim = (x) => String(Math.round(x * 10) / 10)
  if (abs >= 1e7) return '₹' + trim(v / 1e7) + 'Cr'
  if (abs >= 1e5) return '₹' + trim(v / 1e5) + 'L'
  if (abs >= 1e3) return '₹' + trim(v / 1e3) + 'k'
  return '₹' + trim(v)
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "2026-09" -> "Sep 2026"
export function monthLabel(ym) {
  if (!ym) return ''
  const [y, m] = ym.split('-')
  return `${MONTHS[Number(m) - 1] ?? m} ${y}`
}

// "2026-09-28" -> "28 Sep 2026"
export function dateLabel(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${Number(d)} ${MONTHS[Number(m) - 1] ?? m} ${y}`
}

// "2026-11-08" -> "8 Nov"
export function dayMonth(iso) {
  if (!iso) return ''
  const [, m, d] = iso.slice(0, 10).split('-')
  return `${Number(d)} ${MONTHS[Number(m) - 1] ?? m}`
}

export function number(n) {
  return Number(n).toLocaleString('en-IN')
}

export function plural(n, one, many) {
  return `${number(n)} ${n === 1 ? one : (many ?? one + 's')}`
}

// "2026-10-17T14:38:00.123" (UTC) -> "17 Oct 2026"; empty for missing values
export function when(iso) {
  return iso ? dateLabel(iso) : 'Never'
}
