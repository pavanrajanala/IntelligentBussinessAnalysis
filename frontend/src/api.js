// Every request to the backend goes through here, so errors look the same everywhere.
// In development Vite proxies /api to FastAPI (see vite.config.js); in production FastAPI serves
// this app itself, so a relative path always works. Cookies carry the login session.
export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export async function api(path, options = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, { credentials: 'same-origin', ...options })
  } catch {
    throw new Error('Cannot reach the server. Check your internet connection and try again.')
  }

  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : (body.detail?.[0]?.msg ?? '')
    } catch {
      /* response had no JSON body */
    }
    // The session ended (cookie expired, account suspended): tell the app to show the sign-in page.
    if (res.status === 401 && !path.startsWith('/api/auth/login')) {
      window.dispatchEvent(new Event('auth:expired'))
    }
    throw new Error(detail || `Something went wrong (${res.status}).`)
  }
  return res.json()
}

export function post(path, body) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export function put(path, body) {
  return api(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export function patch(path, body) {
  return api(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}
