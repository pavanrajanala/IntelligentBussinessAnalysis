import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../components/useApi'
import { Loading, Problem } from '../components/Empty'
import UploadPanel from '../components/UploadPanel'
import CleaningReport from '../components/CleaningReport'
import { useAuth } from '../auth'
import { navigate } from '../router'
import { dateLabel, number, plural } from '../format'

export default function Data() {
  const { summary, refresh } = useAuth()
  const uploads = useApi('/api/uploads')
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)

  async function done(result) {
    setReport(result.cleaning_report)
    await refresh()
    uploads.reload()
  }

  async function removeAll() {
    setError('')
    try {
      await api('/api/data', { method: 'DELETE' })
      setConfirm(false)
      setReport(null)
      await refresh()
      uploads.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  const has = summary?.has_data
  return (
    <>
      <header className="page-head">
        <h1>My data</h1>
        <p>
          {has
            ? `${plural(summary.rows, 'sale')} from ${dateLabel(summary.date_start)} to ${dateLabel(summary.date_end)}, across ${plural(summary.products, 'product')}.`
            : 'Add your sales file to get started. Nothing is shared with other customers.'}
        </p>
      </header>

      <section className="block">
        <div className="block__head"><h2>{has ? 'Add or replace sales' : 'Upload your sales'}</h2></div>
        <UploadPanel hasData={has} onUploaded={done} />
      </section>

      {report && (
        <section className="block">
          <div className="block__head"><h2>What we cleaned</h2></div>
          <CleaningReport report={report} />
          <div className="toolbar" style={{ marginTop: 16 }}>
            <button className="btn btn--primary" onClick={() => navigate('/orders')}>See my order list</button>
          </div>
        </section>
      )}

      <section className="block">
        <div className="block__head"><h2>Upload history</h2></div>
        {uploads.loading && <Loading />}
        {uploads.error && <Problem message={uploads.error} onRetry={uploads.reload} />}
        {uploads.data?.length === 0 && <p className="muted">No uploads yet.</p>}
        {uploads.data?.length > 0 && (
          <div className="ledger-wrap">
            <table className="ledger">
              <thead><tr><th className="left">File</th><th className="left">When</th><th className="left">Mode</th><th>Rows saved</th></tr></thead>
              <tbody>
                {uploads.data.map((u) => (
                  <tr key={u.id}>
                    <td className="left">{u.filename}</td>
                    <td className="left">{dateLabel(u.created_at)}</td>
                    <td className="left">{u.mode === 'append' ? 'Added' : 'Replaced'}</td>
                    <td>{number(u.rows_saved)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {has && (
        <div className="danger-zone">
          <h2>Remove my sales data</h2>
          <p>This deletes every sale saved in your account. Your login and shop details stay.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          {confirm ? (
            <div className="toolbar">
              <button className="btn btn--danger" onClick={removeAll}>Yes, remove it all</button>
              <button className="btn btn--quiet" onClick={() => setConfirm(false)}>Keep it</button>
            </div>
          ) : (
            <button className="btn btn--secondary" onClick={() => setConfirm(true)}>Remove all my data</button>
          )}
        </div>
      )}
    </>
  )
}
