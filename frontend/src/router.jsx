import { useEffect, useState } from 'react'

// A very small hash router: the page is whatever follows "#" in the address (#/orders, #/ask ...).
// Hash routing means the backend needs no special rules for page addresses.

function parse() {
  const raw = window.location.hash.replace(/^#/, '') || '/'
  const [path] = raw.split('?')
  return path || '/'
}

export function useRoute() {
  const [path, setPath] = useState(parse)
  useEffect(() => {
    const onChange = () => setPath(parse())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return path
}

export function navigate(path) {
  window.location.hash = path
  window.scrollTo({ top: 0 })
}

export function Link({ to, children, ...rest }) {
  return (
    <a href={`#${to}`} {...rest}>
      {children}
    </a>
  )
}

// A question handed from one page to the Ask page ("Ask why" buttons).
let pendingQuestion = null
export function askAssistant(question) {
  pendingQuestion = question
  navigate('/ask')
}
export function takePendingQuestion() {
  const q = pendingQuestion
  pendingQuestion = null
  return q
}
