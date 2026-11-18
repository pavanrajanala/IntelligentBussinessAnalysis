import { useState } from 'react'
import { useAuth } from './auth'
import { useRoute, navigate, Link } from './router'
import { Wordmark } from './components/Brand'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Overview from './pages/Overview'
import OrderList from './pages/OrderList'
import Season from './pages/Season'
import Ask from './pages/Ask'
import Data from './pages/Data'
import Account from './pages/Account'
import Admin from './pages/Admin'

const NAV = [
  ['/', 'Overview'],
  ['/orders', 'Order list'],
  ['/season', 'Season and festivals'],
  ['/ask', 'Ask'],
  ['/data', 'My data'],
]

const PAGES = { '/': Overview, '/orders': OrderList, '/season': Season, '/ask': Ask, '/data': Data, '/account': Account, '/admin': Admin }

export default function App() {
  const { loading, user, error, summary } = useAuth()
  const route = useRoute()

  if (loading) return <div className="status" role="status">Loading…</div>

  if (!user) {
    if (route === '/signup') return <Signup />
    if (route !== '/login') {
      // Anyone not signed in lands on the sign-in page.
      queueMicrotask(() => navigate('/login'))
    }
    return <Login notice={error} />
  }

  if (route === '/login' || route === '/signup') {
    queueMicrotask(() => navigate(summary?.has_data ? '/' : '/data'))
    return null
  }
  return <Shell route={route} />
}

function Shell({ route }) {
  const { user, profile, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const isAdmin = user.role === 'admin'
  const Page = PAGES[route] && (route !== '/admin' || isAdmin) ? PAGES[route] : Overview
  const current = PAGES[route] && (route !== '/admin' || isAdmin) ? route : '/'

  const item = ([to, label]) => (
    <Link key={to} to={to} aria-current={current === to ? 'page' : undefined} onClick={() => setOpen(false)}>
      {label}
    </Link>
  )

  return (
    <div className="shell">
      <header className="topbar">
        <Wordmark />
        <button className="btn btn--secondary btn--small" aria-expanded={open} aria-controls="sidebar" onClick={() => setOpen((o) => !o)}>
          {open ? 'Close' : 'Menu'}
        </button>
      </header>
      <aside className={`sidebar ${open ? 'is-open' : ''}`} id="sidebar">
        <Wordmark />
        <nav className="nav" aria-label="Main">
          {NAV.map(item)}
          <span className="nav__sep" />
          {item(['/account', 'Account'])}
          {isAdmin && item(['/admin', 'Admin'])}
        </nav>
        <div className="sidebar__foot">
          <strong>{profile?.business_name || user.name}</strong>
          <span>{user.email}</span>
          <button className="link-button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main" id="main">
        <Page />
      </main>
    </div>
  )
}
