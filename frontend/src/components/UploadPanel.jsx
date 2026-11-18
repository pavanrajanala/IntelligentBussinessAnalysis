import { useState } from 'react'
import { API_BASE, api } from '../api'

const MAX_MB = 10

// Choose a CSV, say whether it replaces or adds to the saved data, upload.
export default function UploadPanel({ onUploaded, hasData }) {
  const [file, setFile] = useState(null)
  const [mode, setMode] = useState('replace')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  function choose(f) {
    setError('')
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) {
      setFile(null)
      setError('That is not a .csv file. In Excel, use File, Save As, and pick CSV.')
      return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setFile(null)
      setError(`That file is larger than ${MAX_MB} MB.`)
      return
    }
    setFile(f)
  }

  async function run(request) {
    setBusy(true)
    setError('')
    try {
      onUploaded(await request())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const upload = () => {
    const form = new FormData()
    form.append('file', file)
    form.append('mode', hasData ? mode : 'replace')
    run(() => api('/api/upload', { method: 'POST', body: form }))
  }

  return (
    <div>
      <div
        className={`dropzone ${dragging ? 'dropzone--active' : ''} ${file ? 'dropzone--filled' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          choose(e.dataTransfer.files?.[0])
        }}
      >
        {file ? (
          <p className="dropzone__file">
            {file.name} <span className="muted small">({(file.size / 1024).toFixed(0)} KB)</span>
          </p>
        ) : (
          <p>Drop your sales file here. It should be a CSV.</p>
        )}
        <input type="file" accept=".csv,text/csv" className="visually-hidden" id="csv-input" onChange={(e) => choose(e.target.files?.[0])} />
        <label htmlFor="csv-input" className="btn btn--secondary btn--small">
          {file ? 'Choose a different file' : 'Choose file'}
        </label>
      </div>

      {hasData && (
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="visually-hidden">What should happen to your existing data</legend>
          <div className="radio-row">
            <label>
              <input type="radio" name="mode" checked={mode === 'replace'} onChange={() => setMode('replace')} />
              <span>
                Replace my data
                <small>Use this when the new file has everything.</small>
              </span>
            </label>
            <label>
              <input type="radio" name="mode" checked={mode === 'append'} onChange={() => setMode('append')} />
              <span>
                Add to my data
                <small>Use this for a new month. Repeated rows are skipped.</small>
              </span>
            </label>
          </div>
        </fieldset>
      )}

      {error && (
        <p className="form-error" role="alert" style={{ marginTop: 14 }}>
          {error}
        </p>
      )}

      <div className="toolbar" style={{ marginTop: 16 }}>
        <button className="btn btn--primary" onClick={upload} disabled={!file || busy}>
          {busy ? 'Cleaning your file…' : 'Upload and clean'}
        </button>
        <button className="btn btn--quiet" onClick={() => run(() => api('/api/load-sample', { method: 'POST' }))} disabled={busy}>
          Try with sample data
        </button>
      </div>

      <p className="muted small" style={{ marginTop: 16, maxWidth: '44em' }}>
        Columns we need: <b>date</b>, <b>product</b>, <b>quantity</b>, <b>price</b>. Helpful extras: <b>category</b>, <b>customer_id</b>, <b>region</b>. Common
        alternatives such as qty or unit_price are understood.{' '}
        <a href={`${API_BASE}/api/sample-csv`} download>
          Download an example file
        </a>
        .
      </p>
    </div>
  )
}
