import { dateLabel, number } from './format'

export function LogoMark() {
  return (
    <svg className="logo__mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="currentColor" />
      <rect x="7" y="17" width="4" height="8" rx="1" fill="#fff" opacity=".7" />
      <rect x="14" y="12" width="4" height="13" rx="1" fill="#fff" opacity=".85" />
      <rect x="21" y="7" width="4" height="18" rx="1" fill="#fff" />
    </svg>
  )
}

export default function Header({ summary, onUploadClick, uploadOpen }) {
  const hasData = summary?.has_data

  return (
    <header className="header">
      <div className="header__inner">
        <div className="logo">
          <LogoMark />
          <div>
            <div className="logo__name">Business Analyst Copilot</div>
            <div className="logo__tag">Sales insights from your own data</div>
          </div>
        </div>

        {hasData && (
          <div className="header__right">
            <div className="data-pill" title="Data currently loaded">
              <span className="data-pill__dot" aria-hidden="true" />
              <span>
                {number(summary.rows)} rows · {dateLabel(summary.date_start)} to {dateLabel(summary.date_end)}
              </span>
            </div>
            <button className="btn btn--secondary" onClick={onUploadClick} aria-expanded={uploadOpen}>
              {uploadOpen ? 'Close' : 'Upload new data'}
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
