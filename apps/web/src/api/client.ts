import type {
  AdminStats,
  AdminUser,
  AvailablePatient,
  ChatReply,
  ConsentDirective,
  ConsentDirectiveCreate,
  ConversationMessage,
  ConversationSession,
  DraftSummary,
  EngagementStats,
  EvidenceItem,
  FaceMatch,
  GraphEdge,
  GraphEvidence,
  GraphNode,
  GraphResponse,
  LoginResponse,
  MemoryCard,
  MemoryCreate,
  MemoryDetail,
  MemoryEdit,
  MemorySummary,
  Notification,
  Person,
  PersonCreate,
  PersonUpdate,
  PatientProfile,
  PatientOnboardingRequest,
  PatientProfileUpdate,
  Relationship,
  RelationItem,
  Revision,
  SafetyEvent,
  Source,
  SourceCreate,
  ThirdPartyConsent,
  ThirdPartyCreate,
  ThirdPartyUpdate,
  TokenResponse,
  User,
  UserCreatePayload,
  UserUpdatePayload,
} from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let accessToken: string | null = null
let refreshToken: string | null = null
let patientScope: string | null = null
let refreshInFlight: Promise<boolean> | null = null

export const ACCESS_KEY = 'remind.access_token'
export const REFRESH_KEY = 'remind.refresh_token'

export function setSessionTokens(access: string | null, refresh: string | null) {
  accessToken = access
  refreshToken = refresh
  if (access && refresh) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  } else {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }
}

export function setPatientScope(patientId: string | null) {
  patientScope = patientId
}

async function refreshSession(): Promise<boolean> {
  if (!refreshToken) return false
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return false
        const body = (await res.json()) as TokenResponse
        setSessionTokens(body.access_token, body.refresh_token)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null
      })
  }
  const refreshed = await refreshInFlight
  if (!refreshed) {
    setSessionTokens(null, null)
    window.dispatchEvent(new Event('remind:session-expired'))
  }
  return refreshed
}

async function request<T>(path: string, init: RequestInit = {}, mayRefresh = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (patientScope) headers.set('X-Patient-ID', patientScope)

  const res = await fetch(`${API_URL}${path}`, { ...init, headers })
  if (
    res.status === 401 &&
    mayRefresh &&
    path !== '/auth/login' &&
    path !== '/auth/refresh' &&
    await refreshSession()
  ) {
    return request<T>(path, init, false)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      detail =
        typeof body.detail === 'string'
          ? body.detail
          : body.detail
            ? JSON.stringify(body.detail)
            : res.statusText
    } catch {
      /* response was not JSON */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

async function requestBlob(path: string, init: RequestInit = {}, mayRefresh = true): Promise<Blob> {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (patientScope) headers.set('X-Patient-ID', patientScope)
  const res = await fetch(`${API_URL}${path}`, { ...init, headers })
  if (res.status === 401 && mayRefresh && await refreshSession()) {
    return requestBlob(path, init, false)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      detail = typeof body.detail === 'string' ? body.detail : res.statusText
    } catch {
      /* response was not JSON */
    }
    throw new ApiError(res.status, detail)
  }
  return res.blob()
}

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  refresh: (refreshToken: string) =>
    request<TokenResponse>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
  me: () => request<User>('/auth/me'),
  availablePatients: () =>
    request<{ items: AvailablePatient[]; count: number }>('/patients/available'),

  patientProfile: () => request<PatientProfile>('/patients/profile'),
  completeOnboarding: (payload: PatientOnboardingRequest) =>
    request<{ profile: PatientProfile; consent: ConsentDirective }>('/patients/onboarding', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updatePatientProfile: (patch: PatientProfileUpdate) =>
    request<PatientProfile>('/patients/profile', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  relationships: () =>
    request<{ items: Relationship[]; count: number }>('/patients/relationships'),
  grantRelationship: (userEmail: string, relationship: string) =>
    request<Relationship>('/patients/relationships', {
      method: 'POST',
      body: JSON.stringify({ user_email: userEmail, relationship }),
    }),
  revokeRelationship: (id: string) =>
    request<{ ok: boolean }>(`/patients/relationships/${id}`, { method: 'DELETE' }),

  timeline: (limit?: number) =>
    request<{ items: MemoryCard[]; count: number }>(`/timeline${limit ? `?limit=${limit}` : ''}`),
  decades: () => request<{ items: { decade: number; count: number; memories: MemoryCard[] }[] }>('/timeline/decades'),
  places: () => request<{ items: { place: string; count: number; memories: MemoryCard[] }[] }>('/timeline/places'),
  engagement: () => request<EngagementStats>('/timeline/engagement'),

  sources: () => request<{ items: Source[]; count: number }>('/sources'),
  createSource: (payload: SourceCreate, patientId?: string) =>
    request<Source>(`/sources${patientId ? `?patient_id=${patientId}` : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  uploadSource: (file: File, contextTags: string[], patientId?: string) => {
    const form = new FormData()
    form.append('file', file, file.name)
    for (const tag of contextTags) form.append('context_tags', tag)
    return request<Source>(
      `/sources/upload${patientId ? `?patient_id=${patientId}` : ''}`,
      { method: 'POST', body: form },
    )
  },
  sourceFileBlob: (id: string) => requestBlob(`/sources/${id}/file`),
  processSource: (id: string) => request<Source>(`/sources/${id}/process`, { method: 'POST' }),
  reconstructSource: (id: string, submit = false) =>
    request<{ items: DraftSummary[]; count: number }>(`/sources/${id}/reconstruct?submit=${submit}`, {
      method: 'POST',
    }),
  deleteSource: (id: string) => request<{ ok: boolean }>(`/sources/${id}`, { method: 'DELETE' }),

  notifications: (unreadOnly = false) =>
    request<{ items: Notification[]; count: number }>(
      `/notifications${unreadOnly ? '?unread=true' : ''}`,
    ),
  markNotificationRead: (id: string) =>
    request<{ ok: boolean }>(`/notifications/${id}/read`, { method: 'POST' }),
  markAllNotificationsRead: () =>
    request<{ ok: boolean; updated: number }>('/notifications/read-all', { method: 'POST' }),

  consentDirectives: (patientId?: string) =>
    request<{ items: ConsentDirective[]; count: number }>(
      `/consent/directives${patientId ? `?patient_id=${patientId}` : ''}`,
    ),
  createDirective: (payload: ConsentDirectiveCreate, patientId?: string) =>
    request<ConsentDirective>(
      `/consent/directives${patientId ? `?patient_id=${patientId}` : ''}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  thirdParties: (patientId?: string) =>
    request<{ items: ThirdPartyConsent[]; count: number }>(
      `/consent/third-parties${patientId ? `?patient_id=${patientId}` : ''}`,
    ),
  createThirdParty: (payload: ThirdPartyCreate, patientId?: string) =>
    request<ThirdPartyConsent>(
      `/consent/third-parties${patientId ? `?patient_id=${patientId}` : ''}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  updateThirdParty: (id: string, patch: ThirdPartyUpdate) =>
    request<ThirdPartyConsent>(`/consent/third-parties/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  deleteThirdParty: (id: string) =>
    request<{ ok: boolean }>(`/consent/third-parties/${id}`, { method: 'DELETE' }),

  adminUsers: () => request<{ items: AdminUser[]; count: number }>('/admin/users'),
  adminCreateUser: (payload: UserCreatePayload) =>
    request<AdminUser>('/admin/users', { method: 'POST', body: JSON.stringify(payload) }),
  adminUpdateUser: (id: string, patch: UserUpdatePayload) =>
    request<AdminUser>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  adminStats: () => request<AdminStats>('/admin/stats'),

  conversationSessions: () =>
    request<{ items: ConversationSession[]; count: number }>('/conversations/sessions'),
  startConversation: (sessionType = 'chat') =>
    request<{ id: string; patient_id: string; session_type: string; status: string }>(
      '/conversations/sessions',
      { method: 'POST', body: JSON.stringify({ session_type: sessionType }) },
    ),
  conversationMessages: (id: string) =>
    request<{ items: ConversationMessage[]; count: number }>(`/conversations/sessions/${id}/messages`),
  sendConversationMessage: (id: string, content: string) =>
    request<ChatReply>(`/conversations/sessions/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
  stopConversation: (id: string) =>
    request<{ ok: boolean; status: string; safety_event?: string }>(
      `/conversations/sessions/${id}/stop`,
      { method: 'POST' },
    ),

  people: (patientId?: string) =>
    request<{ items: Person[]; count: number }>(`/people${patientId ? `?patient_id=${patientId}` : ''}`),
  createPerson: (payload: PersonCreate, patientId?: string) =>
    request<Person>(`/people${patientId ? `?patient_id=${patientId}` : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updatePerson: (id: string, patch: PersonUpdate) =>
    request<Person>(`/people/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  personRelations: (id: string) =>
    request<{ items: RelationItem[] }>(`/people/${id}/relations`),
  faceMatches: (patientId?: string) =>
    request<{ items: FaceMatch[]; count: number }>(`/people/face-matches${patientId ? `?patient_id=${patientId}` : ''}`),
  confirmFaceMatch: (id: string, personId: string) =>
    request<{ ok: boolean; face_match_state: string; person_identity_status: string }>(
      `/people/face-matches/${id}/confirm`,
      { method: 'POST', body: JSON.stringify({ person_id: personId }) },
    ),

  graph: (patientId?: string) =>
    request<GraphResponse>(`/graph${patientId ? `?patient_id=${patientId}` : ''}`),
  graphNodes: (patientId?: string, nodeType?: string, name?: string) => {
    const params = new URLSearchParams()
    if (patientId) params.set('patient_id', patientId)
    if (nodeType) params.set('node_type', nodeType)
    if (name) params.set('name', name)
    const qs = params.toString()
    return request<{ items: GraphNode[]; count: number }>(`/graph/nodes${qs ? `?${qs}` : ''}`)
  },
  createGraphNode: (
    payload: { node_type: string; name: string; metadata?: Record<string, unknown> },
    patientId?: string,
  ) =>
    request<GraphNode>(
      `/graph/nodes${patientId ? `?patient_id=${patientId}` : ''}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  createGraphEdge: (
    payload: {
      source_node_id: string
      target_node_id: string
      relation_type: string
      weight?: number
      confidence?: number | null
    },
    patientId?: string,
  ) =>
    request<GraphEdge>(
      `/graph/edges${patientId ? `?patient_id=${patientId}` : ''}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  reviewGraphEdge: (id: string, status: string, disputed = false) =>
    request<GraphEdge>(`/graph/edges/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ status, disputed }),
    }),
  traceGraphEdge: (id: string) =>
    request<{ items: GraphEvidence[] }>(`/graph/edges/${id}/trace`),

  safetyEvents: (unacknowledgedOnly = false, patientId?: string) => {
    const params = new URLSearchParams()
    if (unacknowledgedOnly) params.set('unacknowledged_only', 'true')
    if (patientId) params.set('patient_id', patientId)
    const qs = params.toString()
    return request<{ items: SafetyEvent[]; count: number }>(`/safety/events${qs ? `?${qs}` : ''}`)
  },
  acknowledgeSafetyEvent: (id: string) =>
    request<{ ok: boolean }>(`/safety/events/${id}/acknowledge`, { method: 'POST' }),
  caregiverStopSession: (id: string) =>
    request<{ ok: boolean; safety_event: string }>(`/safety/sessions/${id}/stop`, {
      method: 'POST',
    }),
  safetyLevel: (patientId?: string) =>
    request<{ patient_id: string; safety_level: string }>(
      `/safety/level${patientId ? `?patient_id=${patientId}` : ''}`,
    ),

  memories: (memStatus?: string) =>
    request<{ items: MemorySummary[]; count: number }>(`/memories${memStatus ? `?mem_status=${memStatus}` : ''}`),
  getMemory: (id: string) => request<MemoryDetail>(`/memories/${id}`),
  createMemory: (payload: MemoryCreate) =>
    request<MemoryDetail>('/memories', { method: 'POST', body: JSON.stringify(payload) }),
  submitMemory: (id: string) => request<MemorySummary>(`/memories/${id}/submit`, { method: 'POST' }),
  approveMemory: (id: string) => request<MemorySummary>(`/memories/${id}/approve`, { method: 'POST' }),
  rejectMemory: (id: string, reason?: string) =>
    request<MemorySummary>(`/memories/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
  disputeMemory: (id: string, reason?: string) =>
    request<MemorySummary>(`/memories/${id}/dispute`, { method: 'POST', body: JSON.stringify({ reason }) }),
  archiveMemory: (id: string) => request<MemorySummary>(`/memories/${id}/archive`, { method: 'POST' }),
  restrictMemory: (id: string, reason?: string) =>
    request<MemorySummary>(`/memories/${id}/restrict`, { method: 'POST', body: JSON.stringify({ reason }) }),
  editMemory: (id: string, payload: MemoryEdit) =>
    request<MemoryDetail>(`/memories/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  getEvidence: (id: string) => request<{ items: EvidenceItem[] }>(`/memories/${id}/evidence`),
  getRevisions: (id: string) => request<{ items: Revision[] }>(`/memories/${id}/revisions`),
}
