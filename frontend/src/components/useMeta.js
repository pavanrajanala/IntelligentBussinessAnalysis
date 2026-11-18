import { useEffect, useState } from 'react'
import { api } from '../api'

// Lists for the forms (shop types, customer types, states). Fetched once and kept.
let cached = null
export function useMeta() {
  const [meta, setMeta] = useState(cached)
  const [error, setError] = useState('')
  useEffect(() => {
    if (cached) return
    api('/api/meta')
      .then((m) => {
        cached = m
        setMeta(m)
      })
      .catch((e) => setError(e.message))
  }, [])
  return { meta, error }
}
