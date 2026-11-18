import { useRef, useState } from 'react'
import { API_BASE, api } from './api'

const MAX_MB = 10

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 16V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  )
}

export default function UploadPanel({ hero = false, onUploaded, onCancel }) {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle') // idle | working | error
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  function choose(f) {
    setError('')
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) {
      setFile(null)
      setError('Please choose a .csv file.')
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
    setStatus('working')
    setError('')
    try {
      onUploaded(await request())
    } catch (err) {
      setStatus('error')
      setError(err.message)
    }
  }

  const upload = () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    run(() => api('/api/upload', { method: 'POST', body: form }))
  }

  const loadSample = () => run(() => api('/api/load-sample', { method: 'POST' }))

  const busy = status === 'working'

  return (
    <section className={`card upload ${hero ? 'upload--hero' : ''}`} aria-labelledby="upload-title">
      {hero ? (
        <div className="upload__intro">
          <h1 id="upload-title" className="upload__heading">
            Turn a sales spreadsheet into answers
          </h1>
          <p className="upload__lead">
            Upload a CSV and the app cleans it automatically, builds a dashboard, and lets you ask questions such as
            “Why is Colgate not selling well?”
          </p>
        </div>
      ) : (
        <h2 id="upload-title" className="card__title">
          Upload new sales data
        </h2>
      )}

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
        <UploadIcon />
        {file ? (
          <p className="dropzone__file">
            <strong>{file.name}</strong>
            <span>{(file.size / 1024).toFixed(0)} KB</span>
          </p>
        ) : (
          <p className="dropzone__text">Drag a CSV file here, or</p>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="visually-hidden"
          id="csv-input"
          onChange={(e) => choose(e.target.files?.[0])}
        />
        <label htmlFor="csv-input" className="btn btn--secondary">
          {file ? 'Choose a different file' : 'Browse files'}
        </label>
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <div className="upload__actions">
        <button className="btn btn--primary" onClick={upload} disabled={!file || busy}>
          {busy ? 'Cleaning and loading…' : 'Upload and analyse'}
        </button>
        <button className="btn btn--ghost" onClick={loadSample} disabled={busy}>
          Use sample data
        </button>
        {onCancel && (
          <button className="btn btn--ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        )}
      </div>

      <div className="upload__format">
        <h3>Expected columns</h3>
        <p>
          <code>date</code> <code>product</code> <code>quantity</code> <code>price</code> are required.{' '}
          <code>category</code> <code>customer_id</code> <code>region</code> are optional but unlock more insights
          (customer switching needs <code>customer_id</code>).{' '}
          <a href={`${API_BASE}/api/sample-csv`} download>
            Download an example file
          </a>
        </p>
      </div>
    </section>
  )
}
