import { dateLabel, number } from './format'

export default function CleaningReport({ report, onDismiss }) {
  const stats = [
    { label: 'Rows received', value: report.original_row_count },
    { label: 'Rows kept', value: report.final_row_count, tone: 'good' },
    { label: 'Duplicates removed', value: report.duplicate_rows_removed },
    { label: 'Missing quantities filled', value: report.rows_with_missing_quantity_filled, note: 'with the product median' },
    { label: 'Unreadable dates dropped', value: report.rows_with_unparseable_dates },
    { label: 'Outliers flagged', value: report.outliers_flagged, note: 'kept, but excluded from totals' },
  ]
  // Only show these when something actually happened.
  if (report.rows_with_invalid_price_dropped) {
    stats.push({ label: 'Invalid prices dropped', value: report.rows_with_invalid_price_dropped })
  }
  if (report.rows_with_invalid_quantity_dropped) {
    stats.push({ label: 'Invalid quantities dropped', value: report.rows_with_invalid_quantity_dropped })
  }
  if (report.rows_missing_product_dropped) {
    stats.push({ label: 'Rows without a product dropped', value: report.rows_missing_product_dropped })
  }

  return (
    <section className="card report" aria-labelledby="report-title">
      <div className="report__head">
        <div>
          <h2 id="report-title" className="card__title">
            Data cleaned automatically
          </h2>
          <p className="card__subtitle">
            {report.date_range && `${dateLabel(report.date_range.start)} to ${dateLabel(report.date_range.end)} · `}
            {report.products} products · {report.customers} customers
          </p>
        </div>
        <button className="btn btn--ghost" onClick={onDismiss}>
          Dismiss
        </button>
      </div>

      <dl className="report__grid">
        {stats.map((s) => (
          <div key={s.label} className={`report__stat ${s.tone === 'good' ? 'report__stat--good' : ''}`}>
            <dt>{s.label}</dt>
            <dd>{number(s.value)}</dd>
            {s.note && <span className="report__note">{s.note}</span>}
          </div>
        ))}
      </dl>

      {report.warnings?.length > 0 && (
        <ul className="report__warnings">
          {report.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
