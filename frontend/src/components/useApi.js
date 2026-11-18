import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

// Load a GET endpoint. `reload()` fetches again. Returns { data, error, loading, reload }.
export function useApi(path) {
  const [state, setState] = useState({ data: null, error: '', loading: true })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    api(path)
      .then((data) => !cancelled && setState({ data, error: '', loading: false }))
      .catch((err) => !cancelled && setState({ data: null, error: err.message, loading: false }))
    return () => {
      cancelled = true
    }
  }, [path, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}
