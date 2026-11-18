import { Link } from '../router'

export function NoData({ what = 'this page' }) {
  return (
    <div className="empty">
      <h2>Nothing to show yet</h2>
      <p>Add your sales file and {what} will fill in. It takes about a minute, and you can try the sample data first.</p>
      <Link to="/data" className="btn btn--primary">Add sales data</Link>
    </div>
  )
}

export function Loading() {
  return <div className="status" role="status">Loading…</div>
}

export function Problem({ message, onRetry }) {
  return (
    <div className="notice notice--error" role="alert">
      {message} {onRetry && <button className="link-button" onClick={onRetry}>Try again</button>}
    </div>
  )
}
