import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Source, SourceCreate as SourceCreatePayload } from '../api/types'
import { INGESTION_ROLES, REVIEW_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge, statusTone } from '../components/Badge'
import { Icon } from '../components/Icon'

const FILE_TYPES = ['photo', 'video', 'audio', 'document', 'message_export']

export function Sources() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'administrator'
  const canReconstruct = user !== null && REVIEW_ROLES.includes(user.role)
  if (user !== null && !INGESTION_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />
  }
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [showUpload, setShowUpload] = useState(false)

  const { data, loading, error, reload } = useApiData(() => api.sources())

  async function act(id: string, fn: () => Promise<unknown>, message: string) {
    setBusyId(id)
    setActionError(null)
    setNotice(null)
    try {
      const res = (await fn()) as { count?: number }
      setNotice(res?.count !== undefined ? `${message} (${res.count})` : message)
      reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setBusyId(null)
    }
  }

  async function removeSource(s: { id: string; file_name: string }) {
    if (!window.confirm(`Delete source "${s.file_name}"?`)) return
    setActionError(null)
    setNotice(null)
    try {
      await api.deleteSource(s.id)
      reload()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed')
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>Sources</h1>
        <div className="row-actions">
          <button type="button" className="btn primary" onClick={() => { setShowUpload(false); setShowForm((v) => !v) }}>
            <Icon name="plus" size={16} />
            {showForm ? 'Cancel' : 'Register source'}
          </button>
          <button type="button" className="btn" onClick={() => { setShowForm(false); setShowUpload((v) => !v) }}>
            <Icon name="upload" size={16} />
            {showUpload ? 'Cancel' : 'Upload file'}
          </button>
        </div>
      </div>
      <p className="muted">
        Uploaded material before it becomes memories. Use structured tags like{' '}
        <code>person:Ramesh</code>, <code>place:Shimla</code>, <code>date:1992</code>.
      </p>

      {showForm && <SourceForm isAdmin={isAdmin} onDone={(ok) => { if (ok) { setShowForm(false); reload() } }} />}
      {showUpload && <UploadForm isAdmin={isAdmin} onDone={(ok) => { if (ok) { setShowUpload(false); reload() } }} />}

      {notice && <p className="success">{notice}</p>}
      {actionError && <p className="error">{actionError}</p>}
      {loading && <p>Loading sources…</p>}
      {error && <p className="error">{error}</p>}

      <div className="list">
        {data?.items.map((s) => (
          <SourceRow
            key={s.id}
            s={s}
            canReconstruct={canReconstruct}
            busyId={busyId}
            onAct={act}
            onRemove={removeSource}
          />
        ))}
        {data && data.items.length === 0 && <p className="muted">No sources yet.</p>}
      </div>
    </section>
  )
}

function useSourceBlob(id: string | null) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let active = true
    let objectUrl: string | null = null
    api
      .sourceFileBlob(id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        if (active) setUrl(objectUrl)
        else URL.revokeObjectURL(objectUrl)
      })
      .catch(() => {
        /* file unavailable — no preview */
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [id])

  return url
}

function SourceRow({
  s,
  canReconstruct,
  busyId,
  onAct,
  onRemove,
}: {
  s: Source
  canReconstruct: boolean
  busyId: string | null
  onAct: (id: string, fn: () => Promise<unknown>, message: string) => void
  onRemove: (s: { id: string; file_name: string }) => void
}) {
  const [dlError, setDlError] = useState<string | null>(null)
  const preview = useSourceBlob(s.storage_path && (s.file_type === 'photo' || s.file_type === 'video') ? s.id : null)

  async function download() {
    setDlError(null)
    try {
      const blob = await api.sourceFileBlob(s.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = s.file_name
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    } catch (e) {
      setDlError(e instanceof ApiError ? e.message : 'Download failed')
    }
  }

  return (
    <div className="row">
      <div className="row-main">
        <div className="row-title">
          {s.file_name}
          <Badge tone={statusTone(s.status)}>{s.status}</Badge>
        </div>
        <div className="row-sub">
          {s.file_type}
          {s.file_size ? ` · ${formatSize(s.file_size)}` : ''}
          {s.pipeline_type ? ` · ${s.pipeline_type}` : ''} · {s.created_at}
        </div>
        {s.context_tags.length > 0 && (
          <div className="chips">
            {s.context_tags.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
        )}
        {preview && <img className="source-preview" src={preview} alt={s.file_name} />}
        {dlError && <p className="error">{dlError}</p>}
      </div>
      <div className="row-actions">
        {s.storage_path && (
          <button type="button" className="btn" onClick={download}>
            <Icon name="download" size={15} /> Download
          </button>
        )}
        {(s.status === 'pending' || s.status === 'queued' || s.status === 'failed') && (
          <button
            type="button"
            className="btn"
            disabled={busyId === s.id}
            onClick={() => onAct(s.id, () => api.processSource(s.id), 'Processing started')}
          >
            {busyId === s.id ? '…' : 'Process'}
          </button>
        )}
        {s.status === 'processing' && <span className="muted">Processing…</span>}
        {s.status === 'completed' && canReconstruct && (
          <>
            <button
              type="button"
              className="btn"
              disabled={busyId === s.id}
              onClick={() => onAct(s.id, () => api.reconstructSource(s.id), 'Drafts created')}
            >
              {busyId === s.id ? '…' : 'Reconstruct'}
            </button>
            <button
              type="button"
              className="btn"
              disabled={busyId === s.id}
              onClick={() =>
                onAct(s.id, () => api.reconstructSource(s.id, true), 'Drafts created & submitted')
              }
            >
              {busyId === s.id ? '…' : 'Reconstruct & submit'}
            </button>
          </>
        )}
        {s.status === 'completed' && !canReconstruct && (
          <span className="muted">Processed — a reviewer can reconstruct</span>
        )}
        <button type="button" className="btn danger" onClick={() => onRemove(s)}>
          <Icon name="trash" size={15} /> Delete
        </button>
      </div>
    </div>
  )
}

function formatSize(bytes: number | null): string {
  if (!bytes || bytes <= 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function UploadForm({ isAdmin, onDone }: { isAdmin: boolean; onDone: (ok: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [tagsText, setTagsText] = useState('')
  const [patientId, setPatientId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!file) {
      setError('Choose a file')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await api.uploadSource(
        file,
        tagsText.split(',').map((t) => t.trim()).filter(Boolean),
        isAdmin ? patientId || undefined : undefined,
      )
      onDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel form" onSubmit={onSubmit}>
      <h2>Upload a file</h2>
      <label>
        File
        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
        />
      </label>
      <label>
        Context tags (comma-separated, e.g. <code>person:Ramesh, place:Shimla</code>)
        <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} placeholder="person:Ramesh, place:Shimla, date:1992" />
      </label>
      {isAdmin && (
        <label>
          Patient id (required for administrators)
          <input value={patientId} onChange={(e) => setPatientId(e.target.value)} />
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Uploading…' : 'Upload'}
        </button>
      </div>
    </form>
  )
}

function SourceForm({ isAdmin, onDone }: { isAdmin: boolean; onDone: (ok: boolean) => void }) {
  const [file_name, setFileName] = useState('')
  const [file_type, setFileType] = useState('photo')
  const [tagsText, setTagsText] = useState('')
  const [capture_date, setCaptureDate] = useState('')
  const [storage_path, setStoragePath] = useState('')
  const [patientId, setPatientId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    const payload: SourceCreatePayload = {
      file_name,
      file_type,
      context_tags: tagsText.split(',').map((t) => t.trim()).filter(Boolean),
      storage_path: storage_path || null,
      capture_date: capture_date || null,
    }
    try {
      await api.createSource(payload, isAdmin ? patientId || undefined : undefined)
      onDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel form" onSubmit={onSubmit}>
      <h2>Register a source</h2>
      <label>
        File name
        <input value={file_name} onChange={(e) => setFileName(e.target.value)} required />
      </label>
      <label>
        Type
        <select value={file_type} onChange={(e) => setFileType(e.target.value)}>
          {FILE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label>
        Context tags (comma-separated, e.g. <code>person:Ramesh, place:Shimla</code>)
        <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} placeholder="person:Ramesh, place:Shimla, date:1992" />
      </label>
      <label>
        Capture date
        <input type="date" value={capture_date} onChange={(e) => setCaptureDate(e.target.value)} />
      </label>
      <label>
        Storage path (optional)
        <input value={storage_path} onChange={(e) => setStoragePath(e.target.value)} />
      </label>
      {isAdmin && (
        <label>
          Patient id (required for administrators)
          <input value={patientId} onChange={(e) => setPatientId(e.target.value)} />
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Registering…' : 'Register'}
        </button>
      </div>
    </form>
  )
}
