import { dateLabel, number } from '../format'

// What the automatic cleaning did to the uploaded file.
export default function CleaningReport({ report }) {
  const items = [
    ['Rows in your file', report.original_row_count],
    ['Rows kept', report.final_row_count],
    ['Duplicates removed', report.duplicate_rows_removed],
    ['Missing quantities filled', report.rows_with_missing_quantity_filled, 'using that item’s usual quantity'],
    ['Unreadable dates dropped', report.rows_with_unparseable_dates],
    ['Unusually large orders', report.outliers_flagged, 'kept, but left out of totals'],
  ]
  if (report.rows_with_invalid_price_dropped) items.push(['Rows with no price dropped', report.rows_with_invalid_price_dropped])
  if (report.rows_with_invalid_quantity_dropped) items.push(['Rows with bad quantity dropped', report.rows_with_invalid_quantity_dropped])
  if (report.rows_missing_product_dropped) items.push(['Rows with no product name dropped', report.rows_missing_product_dropped])

  return (
    <>
      <p className="muted small" style={{ marginBottom: 8 }}>
        {report.date_range && `${dateLabel(report.date_range.start)} to ${dateLabel(report.date_range.end)}. `}
        {report.products} products, {report.customers} customers.
        {report.rows_in_account ? ` Your account now holds ${number(report.rows_in_account)} rows.` : ''}
      </p>
      <dl className="report">
        {items.map(([label, value, note]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{number(value)}</dd>
            {note && <small>{note}</small>}
          </div>
        ))}
      </dl>
      {report.warnings?.length > 0 && (
        <ul className="small muted" style={{ marginTop: 10, paddingLeft: 18 }}>
          {report.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </>
  )
}
