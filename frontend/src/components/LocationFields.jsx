import { useState } from 'react'
import { getPosition, reverseGeocode } from './location'

// State, city, pincode, plus a "use my location" button. `value` and `onChange` are the parent's form state.
export default function LocationFields({ value, onChange, states }) {
  const [status, setStatus] = useState({ kind: 'idle', text: '' })

  const set = (patch) => onChange({ ...value, ...patch })

  async function useMyLocation() {
    setStatus({ kind: 'busy', text: 'Finding your location…' })
    try {
      const { latitude, longitude } = await getPosition()
      try {
        const place = await reverseGeocode(latitude, longitude, states)
        set({ latitude, longitude, state: place.state || value.state, city: place.city || value.city, pincode: place.pincode || value.pincode })
        setStatus({
          kind: 'ok',
          text: place.state ? `Found: ${[place.city, place.state].filter(Boolean).join(', ')}. Check it below and correct it if needed.` : 'Location saved. Please choose your state below.',
        })
      } catch {
        set({ latitude, longitude })
        setStatus({ kind: 'ok', text: 'Location saved, but the place name could not be looked up. Please choose your state below.' })
      }
    } catch (err) {
      setStatus({ kind: 'error', text: err.message })
    }
  }

  return (
    <>
      <div className="locate">
        <p>Your location tells us which festivals and which season apply to your shop. It is never shown to other customers.</p>
        <button type="button" className="btn btn--secondary btn--small" onClick={useMyLocation} disabled={status.kind === 'busy'}>
          {value.latitude ? 'Update my location' : 'Use my current location'}
        </button>
        {status.text && (
          <p className={status.kind === 'error' ? 'small' : 'small muted'} role="status" style={{ margin: '10px 0 0', color: status.kind === 'error' ? 'var(--chilli)' : undefined }}>
            {status.text}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="loc-state">State</label>
        <select id="loc-state" className="select" value={value.state} onChange={(e) => set({ state: e.target.value })}>
          <option value="">Choose your state</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div className="form-row">
        <div className="field">
          <label htmlFor="loc-city">City or town</label>
          <input id="loc-city" className="input" value={value.city} onChange={(e) => set({ city: e.target.value })} autoComplete="address-level2" />
        </div>
        <div className="field">
          <label htmlFor="loc-pin">Pincode</label>
          <input id="loc-pin" className="input" inputMode="numeric" maxLength={6} value={value.pincode} onChange={(e) => set({ pincode: e.target.value.replace(/\D/g, '') })} autoComplete="postal-code" />
        </div>
      </div>
    </>
  )
}
