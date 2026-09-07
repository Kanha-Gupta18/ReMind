import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { Admin } from './pages/Admin'
import { Chat } from './pages/Chat'
import { Consent } from './pages/Consent'
import { Dashboard } from './pages/Dashboard'
import { Decades } from './pages/Decades'
import { Graph } from './pages/Graph'
import { Login } from './pages/Login'
import { MemoryDetail } from './pages/MemoryDetail'
import { People } from './pages/People'
import { Places } from './pages/Places'
import { Review } from './pages/Review'
import { Safety } from './pages/Safety'
import { Sources } from './pages/Sources'
import { Timeline } from './pages/Timeline'

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="muted">Checking session…</p>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route path="/" element={<Timeline />} />
            <Route path="/decades" element={<Decades />} />
            <Route path="/places" element={<Places />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/people" element={<People />} />
            <Route path="/graph" element={<Graph />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/review" element={<Review />} />
            <Route path="/consent" element={<Consent />} />
            <Route path="/safety" element={<Safety />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="/memories/:id" element={<MemoryDetail />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
