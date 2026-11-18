// Finding where the shop is. Everything here is optional: if the browser, the permission or the
// lookup service is unavailable, the person simply picks their state from the list.

export function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('This browser cannot share your location. Please choose your state below.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: Number(pos.coords.latitude.toFixed(5)), longitude: Number(pos.coords.longitude.toFixed(5)) }),
      (err) =>
        reject(
          new Error(
            err.code === 1
              ? 'Location permission was not given. You can choose your state below instead.'
              : 'Could not find your location. Please choose your state below.',
          ),
        ),
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 },
    )
  })
}

const normalise = (s) =>
  String(s || '')
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/national capital territory of|nct of/g, '')
    .replace(/\s+/g, ' ')
    .trim()

const ALIASES = { orissa: 'odisha', pondicherry: 'puducherry' }

export function matchState(name, states) {
  let n = normalise(name)
  n = ALIASES[n] ?? n
  return states.find((s) => normalise(s) === n) ?? states.find((s) => n && (normalise(s).includes(n) || n.includes(normalise(s)))) ?? ''
}

// OpenStreetMap's free Nominatim service turns coordinates into a place name.
export async function reverseGeocode(latitude, longitude, states) {
  const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&zoom=12&accept-language=en&lat=${latitude}&lon=${longitude}`
  const res = await fetch(url)
  if (!res.ok) throw new Error('lookup failed')
  const a = (await res.json()).address ?? {}
  const pin = String(a.postcode ?? '').replace(/\s/g, '')
  return {
    state: matchState(a.state, states),
    city: a.city || a.town || a.village || a.suburb || a.county || a.state_district || '',
    pincode: /^\d{6}$/.test(pin) ? pin : '',
  }
}
