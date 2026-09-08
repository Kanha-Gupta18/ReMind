import { useCallback, useEffect, useState } from 'react'
import { ApiError } from './client'

interface ApiDataState<T> {
  data: T | null
  loading: boolean
  error: string | null
  errorStatus: number | null
  reload: () => void
}

export function useApiData<T>(load: () => Promise<T>, deps: unknown[] = []): ApiDataState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setErrorStatus(null)
    load()
      .then((d) => {
        if (active) setData(d)
      })
      .catch((e: unknown) => {
        if (active) {
          setError(e instanceof Error ? e.message : 'Request failed')
          setErrorStatus(e instanceof ApiError ? e.status : null)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])

  return { data, loading, error, errorStatus, reload }
}
