// The mark is a page of a ledger: ruled lines with one marigold line, the one you act on.
export function Mark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="6" fill="#f59e42" />
      <rect x="7" y="9" width="18" height="2.4" rx="1.2" fill="#ffffff" />
      <rect x="7" y="15" width="18" height="2.4" rx="1.2" fill="#33261a" />
      <rect x="7" y="21" width="12" height="2.4" rx="1.2" fill="#ffffff" />
    </svg>
  )
}

export function Wordmark({ href = '#/' }) {
  return (
    <a className="wordmark" href={href} aria-label="Intelligent Business Analyst home">
      <Mark />
      <span>Intelligent Business Analyst</span>
    </a>
  )
}
