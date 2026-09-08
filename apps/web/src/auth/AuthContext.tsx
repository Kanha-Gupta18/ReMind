import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ACCESS_KEY, api, REFRESH_KEY, setPatientScope, setSessionTokens } from '../api/client'
import type { User } from '../api/types'

const PATIENT_KEY = 'remind.patient_id'

interface AuthContextValue {
  user: User | null
  loading: boolean
  selectedPatientId: string | null
  selectPatient: (patientId: string) => void
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null)

  const clearSession = useCallback(() => {
    setSessionTokens(null, null)
    setPatientScope(null)
    localStorage.removeItem(PATIENT_KEY)
    setSelectedPatientId(null)
    setUser(null)
  }, [])

  const applyPatientSelection = useCallback((nextUser: User) => {
    const stored = localStorage.getItem(PATIENT_KEY)
    const selected = nextUser.role === 'patient'
      ? nextUser.id
      : stored && nextUser.patient_ids.includes(stored)
        ? stored
        : nextUser.patient_ids.length === 1
          ? nextUser.patient_ids[0]
          : null
    setSelectedPatientId(selected)
    setPatientScope(selected)
    if (selected) localStorage.setItem(PATIENT_KEY, selected)
  }, [])

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_KEY)
    const refresh = localStorage.getItem(REFRESH_KEY)
    if (!token || !refresh) {
      setLoading(false)
      return
    }
    setSessionTokens(token, refresh)
    api
      .me()
      .then((nextUser) => {
        setUser(nextUser)
        applyPatientSelection(nextUser)
      })
      .catch(clearSession)
      .finally(() => setLoading(false))

    window.addEventListener('remind:session-expired', clearSession)
    return () => window.removeEventListener('remind:session-expired', clearSession)
  }, [applyPatientSelection, clearSession])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password)
    setSessionTokens(res.access_token, res.refresh_token)
    setUser(res.user)
    applyPatientSelection(res.user)
    return res.user
  }, [applyPatientSelection])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* still clear local state even if the network call fails */
    }
    clearSession()
  }, [clearSession])

  const selectPatient = useCallback((patientId: string) => {
    if (!user?.patient_ids.includes(patientId)) return
    localStorage.setItem(PATIENT_KEY, patientId)
    setSelectedPatientId(patientId)
    setPatientScope(patientId)
  }, [user])

  const value = useMemo(
    () => ({ user, loading, selectedPatientId, selectPatient, login, logout }),
    [user, loading, selectedPatientId, selectPatient, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
