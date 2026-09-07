export type Role =
  | 'patient'
  | 'family_contributor'
  | 'family_reviewer'
  | 'caregiver'
  | 'guardian'
  | 'clinician'
  | 'administrator'

export const ANALYTICS_ROLES: Role[] = ['caregiver', 'clinician', 'guardian', 'administrator']
export const INGESTION_ROLES: Role[] = ['family_contributor', 'family_reviewer', 'guardian', 'administrator']
export const REVIEW_ROLES: Role[] = ['family_reviewer', 'guardian', 'administrator']
export const RESTRICT_ROLES: Role[] = ['caregiver', 'guardian', 'clinician', 'administrator']
export const CREATE_MEMORY_ROLES: Role[] = [
  'patient',
  'family_contributor',
  'family_reviewer',
  'guardian',
]
export const SIGN_ROLES: Role[] = ['patient', 'guardian', 'administrator']
export const MANAGE_CONSENT_ROLES: Role[] = ['guardian', 'administrator']
export const ADMIN_ROLES: Role[] = ['administrator']
export const CHAT_READ_ROLES: Role[] = [
  'patient',
  'family_reviewer',
  'caregiver',
  'guardian',
  'clinician',
  'administrator',
]
export const PEOPLE_CREATE_ROLES: Role[] = ['family_contributor', 'family_reviewer', 'guardian', 'administrator']
export const PEOPLE_EDIT_ROLES: Role[] = ['family_reviewer', 'guardian', 'administrator']
export const GRAPH_CREATE_ROLES: Role[] = [
  'family_contributor',
  'family_reviewer',
  'guardian',
  'administrator',
  'clinician',
  'caregiver',
]
export const GRAPH_READ_ROLES: Role[] = [
  'family_contributor',
  'family_reviewer',
  'guardian',
  'administrator',
  'clinician',
  'caregiver',
]
export const GRAPH_REVIEW_ROLES: Role[] = ['family_reviewer', 'guardian', 'administrator']
export const SAFETY_ROLES: Role[] = ['caregiver', 'clinician', 'guardian', 'administrator']

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  patient_id: string | null
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface MemoryCard {
  id: string
  title: string
  memory_date: string | null
  date_accuracy: string
  confidence_score: number
  sensitivity_flags: string[]
  tags: string[]
  media_urls: string[]
  narrative: string
  created_at: string
}

export interface TimelineResponse {
  items: MemoryCard[]
  count: number
}

export interface DecadeGroup {
  decade: number
  count: number
  memories: MemoryCard[]
}

export interface PlaceGroup {
  place: string
  count: number
  memories: MemoryCard[]
}

export interface EngagementStats {
  total_engagements: number
  by_action: Record<string, number>
  top_memories: { memory_card_id: string; views: number }[]
}

export interface Source {
  id: string
  patient_id: string
  file_name: string
  file_type: string
  file_size: number | null
  storage_path: string | null
  status: string
  pipeline_type: string | null
  context_tags: string[]
  created_at: string
  completed_at: string | null
}

export interface SourceCreate {
  file_name: string
  file_type: string
  context_tags: string[]
  storage_path?: string | null
  capture_date?: string | null
  checksum?: string | null
}

export interface MemorySummary {
  id: string
  patient_id: string
  title: string
  status: string
  visibility: string
  date_accuracy: string | null
  confidence_score: number
  confidence_band: string | null
  sensitivity_flags: string[]
  tags: string[]
  memory_date: string | null
  created_by: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
}

export interface MemoryDetail extends MemorySummary {
  narrative: string
  media_urls: string[]
  contradictions: string[]
  confidence_breakdown: Record<string, unknown> | null
  model_version: string | null
}

export interface MemoryCreate {
  title: string
  narrative?: string | null
  memory_date?: string | null
  date_accuracy?: string | null
  tags?: string[]
  sensitivity_flags?: string[]
  visibility?: string | null
  media_urls?: string[]
}

export interface MemoryEdit {
  title?: string
  narrative?: string
  tags?: string[]
  note?: string
}

export interface EvidenceItem {
  id: string
  claim: string
  evidence_type: string
  confidence: number | null
  review_status: string
  source_file: string | null
}

export interface Revision {
  revision_number: number
  status: string
  content: Record<string, unknown> | null
  authored_by: string | null
  created_at: string
}

export interface DraftSummary {
  id: string
  title: string
  confidence_score: number
  status: string
}

export interface Notification {
  id: string
  type: string
  message: string
  read: boolean
  created_at: string
}

export interface ConsentDirective {
  id: string
  patient_id: string
  version: number
  valid_from: string
  supersedes_id: string | null
  permissions: Record<string, unknown>
  restrictions: Record<string, unknown>
  guardian_rules: Record<string, unknown>
  signer: string | null
  witness: string | null
  training_opt_in: boolean
  post_death_policy: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ConsentDirectiveCreate {
  permissions?: Record<string, unknown>
  restrictions?: Record<string, unknown>
  guardian_rules?: Record<string, unknown>
  signer?: string | null
  witness?: string | null
  training_opt_in?: boolean
  post_death_policy?: Record<string, unknown> | null
}

export interface ThirdPartyConsent {
  id: string
  patient_id: string
  person_id: string | null
  person_name: string
  contact: string | null
  consent_given: boolean
  notes: string | null
  created_at: string
}

export interface ThirdPartyCreate {
  person_name: string
  person_id?: string | null
  contact?: string | null
  consent_given?: boolean
  notes?: string | null
}

export interface ThirdPartyUpdate {
  person_name?: string
  person_id?: string | null
  contact?: string | null
  consent_given?: boolean
  notes?: string | null
}

export interface AdminUser {
  id: string
  email: string
  full_name: string
  role: Role
  patient_id: string | null
  phone: string | null
  mfa_enabled: boolean
  is_active: boolean
  created_at: string
}

export interface UserCreatePayload {
  email: string
  full_name: string
  role: string
  password: string
  patient_id?: string | null
}

export interface UserUpdatePayload {
  full_name?: string
  role?: string
  password?: string
  patient_id?: string | null
  is_active?: boolean
}

export interface AdminStats {
  users_by_role: Record<string, number>
  total_users: number
  total_sources: number
  total_memories: number
}

export interface ConversationSession {
  id: string
  patient_id: string
  session_type: string
  status: string
  started_at: string
  ended_at: string | null
}

export interface ConversationMessage {
  id: string
  role: string
  content: string
  tool_calls: Record<string, unknown>[] | null
  safety_flag: boolean
  created_at: string
}

export interface ChatReply {
  reply: string
  tool_calls: Record<string, unknown>[]
  safety_flag: boolean
}

export interface Person {
  id: string
  patient_id: string
  name: string
  aliases: string[]
  relationship_to_patient: string | null
  identity_status: string
  notes: string | null
  created_at: string
}

export interface PersonCreate {
  name: string
  aliases?: string[]
  relationship_to_patient?: string | null
  notes?: string | null
}

export interface PersonUpdate {
  aliases?: string[]
  relationship_to_patient?: string | null
  identity_status?: string
  notes?: string | null
}

export interface FaceMatch {
  id: string
  source_id: string
  person_id: string | null
  face_match_state: string
  confidence: number
  model_version: string | null
  reviewed_by: string | null
  reviewed_at: string | null
}

export interface RelationItem {
  other_name: string
  other_node_type: string
  relation_type: string
  status: string
  confidence: number | null
}

export interface GraphNode {
  id: string
  node_type: string
  name: string
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface GraphEdge {
  id: string
  patient_id: string
  source_node_id: string
  target_node_id: string
  relation_type: string
  weight: number
  confidence: number | null
  status: string
  disputed: boolean
  reviewed_by: string | null
  reviewed_at: string | null
  evidence_ids: string[]
  model_version: string | null
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphEvidence {
  id: string
  source_data_ref: string
  contribution: string
  detail: string
}

export interface SafetyEvent {
  id: string
  event_type: string
  severity: string
  context: Record<string, unknown> | null
  action_taken: string | null
  session_id: string | null
  acknowledged_by: string | null
  acknowledged_at: string | null
  created_at: string
}
