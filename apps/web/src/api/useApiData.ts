import { useCallback, useEffect, useState } from 'react'

interface ApiDataState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useApiData<T>(load: () => Promise<T>, deps: unknown[] = []): ApiDataState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    load()
      .then((d) => {
        if (active) setData(d)
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : 'Request failed')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])

  return { data, loading, error, reload }
}
