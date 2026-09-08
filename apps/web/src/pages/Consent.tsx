import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { ConsentAction, ConsentDirective, ConsentPermissions, ConsentRestrictions, GuardianRules, PostDeathPolicy, Role, SourceType, ThirdPartyConsent } from '../api/types'
import { MANAGE_CONSENT_ROLES, SIGN_ROLES } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'
import { Badge } from '../components/Badge'
import { Icon } from '../components/Icon'

const SOURCE_OPTIONS: Array<[SourceType, string]> = [['photo', 'Photos'], ['video', 'Videos'], ['audio', 'Audio'], ['document', 'Documents'], ['message_export', 'Message exports']]
const DELEGATED_ROLES: Array<[Role, string]> = [['family_contributor', 'Family contributor'], ['family_reviewer', 'Family reviewer'], ['caregiver', 'Caregiver'], ['guardian', 'Guardian'], ['clinician', 'Clinician']]
const ACTION_OPTIONS: Array<[ConsentAction, string]> = [
  ['profile:view', 'View profile'], ['profile:edit', 'Edit profile'], ['relationships:view', 'View relationships'], ['relationships:manage', 'Manage relationships'],
  ['consent:view', 'View consent'], ['consent:manage', 'Manage consent'], ['sources:view', 'View sources'], ['sources:upload', 'Upload sources'],
  ['sources:process', 'Process sources'], ['sources:delete', 'Delete sources'], ['memories:view', 'View memories'], ['memories:create', 'Create memories'],
  ['memories:edit', 'Edit memories'], ['memories:review', 'Review memories'], ['people:view', 'View people'], ['people:create', 'Create people'],
  ['people:verify', 'Verify identities'], ['graph:view', 'View knowledge graph'], ['graph:edit', 'Edit knowledge graph'], ['graph:review', 'Review graph claims'],
  ['conversations:view', 'View conversations'], ['safety:view', 'View safety events'], ['safety:manage', 'Manage safety controls'], ['engagement:view', 'View engagement'],
]
const SENSITIVITY_OPTIONS = ['DEATH', 'BEREAVEMENT', 'TRAUMA', 'ABUSE', 'ESTRANGEMENT', 'DIVORCE', 'FAMILY_CONFLICT', 'SERIOUS_ILLNESS', 'ACCIDENT', 'WAR', 'VIOLENCE', 'OTHER_RESTRICTED']
const EMPTY_PERMISSIONS: ConsentPermissions = { allowed_data_sources: [], role_actions: {}, third_party_visibility: 'consented_only' }
const EMPTY_RESTRICTIONS: ConsentRestrictions = { prohibited_data_categories: [], blocked_person_ids: [] }
const EMPTY_GUARDIAN: GuardianRules = { guardian_id: null, authority: 'none', allowed_actions: [] }
const EMPTY_POST_DEATH: PostDeathPolicy = { mode: 'keep_private', beneficiary_user_id: null, retention_days: null }

export function Consent() {
  const { user, selectedPatientId } = useAuth()
  const canSign = user !== null && SIGN_ROLES.includes(user.role)
  const canManage = user !== null && MANAGE_CONSENT_ROLES.includes(user.role)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const directives = useApiData(() => api.consentDirectives(), [selectedPatientId])
  const thirdParties = useApiData(() => api.thirdParties(), [selectedPatientId])
  const current = useMemo(() => directives.data?.items.reduce<ConsentDirective | undefined>((latest, item) => !latest || item.version > latest.version ? item : latest, undefined), [directives.data])

  function reload() { directives.reload(); thirdParties.reload() }
  async function act(fn: () => Promise<unknown>, message: string) {
    setActionError(null); setNotice(null)
    try { await fn(); setNotice(message); reload() }
    catch (caught) { setActionError(caught instanceof ApiError ? caught.message : 'The request could not be completed.') }
  }

  return <section>
    <div className="page-head"><div><h1>Consent and permissions</h1><p className="lead">The current signed version controls who can use each part of the patient archive.</p></div></div>
    {notice && <p className="success" role="status">{notice}</p>}
    {actionError && <p className="error" role="alert">{actionError}</p>}
    <div className="group">
      <div className="page-head"><h2>Signed directives</h2></div>
      {canSign && <SignDirective current={current} isGuardian={user?.role === 'guardian'} onDone={() => { setNotice('A new consent version was signed.'); reload() }} />}
      {directives.loading && <p className="muted">Loading directives...</p>}
      {directives.error && <p className="error" role="alert">{directives.error}</p>}
      {directives.data?.items.length === 0 && <p className="muted">No directive has been signed yet.</p>}
      {directives.data && <div className="list">{[...directives.data.items].sort((a, b) => b.version - a.version).map((directive) => <DirectiveCard key={directive.id} directive={directive} current={directive.id === current?.id} />)}</div>}
    </div>
    <div className="group">
      <div className="page-head"><div><h2>People shown in the archive</h2><p className="lead">Record whether each third party has agreed to appear.</p></div></div>
      {canManage && <AddThirdParty onDone={reload} />}
      {thirdParties.loading && <p className="muted">Loading consent records...</p>}
      {thirdParties.error && <p className="error" role="alert">{thirdParties.error}</p>}
      {thirdParties.data?.items.length === 0 && <p className="muted">No third-party records yet.</p>}
      {thirdParties.data && <div className="list">{thirdParties.data.items.map((record) => <ThirdPartyRow key={record.id} record={record} canManage={canManage} onAct={act} />)}</div>}
    </div>
  </section>
}

function DirectiveCard({ directive, current }: { directive: ConsentDirective; current: boolean }) {
  const roles = Object.entries(directive.permissions.role_actions).filter(([, actions]) => actions && actions.length > 0)
  return <article className="row directive-card"><div className="row-main">
    <div className="row-title">Version {directive.version}<Badge tone={current ? 'green' : 'neutral'}>{current ? 'current' : 'superseded'}</Badge></div>
    <p className="row-sub">Signed {new Date(directive.valid_from).toLocaleString()}{directive.signer ? ` by ${directive.signer}` : ''}</p>
    <dl className="directive-summary">
      <div><dt>Sources</dt><dd>{directive.permissions.allowed_data_sources.join(', ') || 'None'}</dd></div>
      <div><dt>Delegated roles</dt><dd>{roles.map(([role, actions]) => `${role.replaceAll('_', ' ')} (${actions?.length ?? 0})`).join(', ') || 'None'}</dd></div>
      <div><dt>Restricted topics</dt><dd>{directive.restrictions.prohibited_data_categories.join(', ') || 'None'}</dd></div>
      <div><dt>Third parties</dt><dd>{directive.permissions.third_party_visibility === 'consented_only' ? 'Only people with recorded consent' : 'People reviewed by family'}</dd></div>
      <div><dt>Guardian authority</dt><dd>{directive.guardian_rules.authority}</dd></div>
      <div><dt>After death</dt><dd>{directive.post_death_policy.mode.replaceAll('_', ' ')}</dd></div>
      <div><dt>Model training</dt><dd>{directive.training_opt_in ? 'Allowed' : 'Not allowed'}</dd></div>
    </dl>
  </div></article>
}

function SignDirective({ current, isGuardian, onDone }: { current?: ConsentDirective; isGuardian: boolean; onDone: () => void }) {
  const [show, setShow] = useState(false)
  const [permissions, setPermissions] = useState<ConsentPermissions>(EMPTY_PERMISSIONS)
  const [restrictions, setRestrictions] = useState<ConsentRestrictions>(EMPTY_RESTRICTIONS)
  const [guardian, setGuardian] = useState<GuardianRules>(EMPTY_GUARDIAN)
  const [postDeath, setPostDeath] = useState<PostDeathPolicy>(EMPTY_POST_DEATH)
  const [witness, setWitness] = useState('')
  const [training, setTraining] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    setPermissions(current?.permissions ?? EMPTY_PERMISSIONS); setRestrictions(current?.restrictions ?? EMPTY_RESTRICTIONS)
    setGuardian(current?.guardian_rules ?? EMPTY_GUARDIAN); setPostDeath(current?.post_death_policy ?? EMPTY_POST_DEATH)
    setWitness(current?.witness ?? ''); setTraining(current?.training_opt_in ?? false)
  }, [current])

  function toggleSource(source: SourceType) { setPermissions((value) => ({ ...value, allowed_data_sources: value.allowed_data_sources.includes(source) ? value.allowed_data_sources.filter((item) => item !== source) : [...value.allowed_data_sources, source] })) }
  function toggleRoleAction(role: Role, action: ConsentAction) {
    setPermissions((value) => { const existing = value.role_actions[role] ?? []; return { ...value, role_actions: { ...value.role_actions, [role]: existing.includes(action) ? existing.filter((item) => item !== action) : [...existing, action] } } })
    if (role === 'guardian' && guardian.allowed_actions.includes(action)) setGuardian((value) => ({ ...value, allowed_actions: value.allowed_actions.filter((item) => item !== action) }))
  }
  function toggleRestricted(category: string) { setRestrictions((value) => ({ ...value, prohibited_data_categories: value.prohibited_data_categories.includes(category) ? value.prohibited_data_categories.filter((item) => item !== category) : [...value.prohibited_data_categories, category] })) }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(null); setBusy(true)
    try {
      await api.createDirective({ permissions, restrictions, guardian_rules: guardian.authority === 'none' ? EMPTY_GUARDIAN : guardian, witness: witness || null, training_opt_in: training, post_death_policy: postDeath })
      setShow(false); onDone()
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : 'The directive could not be signed.') }
    finally { setBusy(false) }
  }

  return <div className="panel consent-editor">
    <div className="page-head"><div><h3>{current ? 'Create a new version' : 'Create the first directive'}</h3><p className="muted">Changes take effect as soon as this version is signed.</p></div><button type="button" className="btn primary" onClick={() => setShow((value) => !value)}><Icon name="plus" size={16} />{show ? 'Cancel' : 'Review permissions'}</button></div>
    {show && <form className="consent-form" onSubmit={submit}>
      {isGuardian && <p className="consent-note">A guardian can make the current directive more restrictive, but cannot expand authority.</p>}
      <fieldset><legend>Allowed source types</legend><div className="choice-grid">{SOURCE_OPTIONS.map(([value, label]) => <Choice key={value} label={label} checked={permissions.allowed_data_sources.includes(value)} onChange={() => toggleSource(value)} />)}</div></fieldset>
      <fieldset><legend>Authority by role</legend><p className="muted">An account still needs an active relationship with this patient.</p><div className="role-permissions">{DELEGATED_ROLES.map(([role, label]) => <details key={role}><summary>{label}<span>{permissions.role_actions[role]?.length ?? 0} allowed</span></summary><div className="choice-grid permission-grid">{ACTION_OPTIONS.map(([action, actionLabel]) => <Choice key={action} label={actionLabel} checked={(permissions.role_actions[role] ?? []).includes(action)} onChange={() => toggleRoleAction(role, action)} />)}</div></details>)}</div></fieldset>
      <fieldset><legend>Restricted topics</legend><div className="choice-grid">{SENSITIVITY_OPTIONS.map((category) => <Choice key={category} label={category.replaceAll('_', ' ').toLowerCase()} checked={restrictions.prohibited_data_categories.includes(category)} onChange={() => toggleRestricted(category)} />)}</div><label>Blocked person IDs<input value={restrictions.blocked_person_ids.join(', ')} onChange={(event) => setRestrictions((value) => ({ ...value, blocked_person_ids: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) }))} placeholder="Separate IDs with commas" /></label></fieldset>
      <fieldset><legend>Guardian authority</legend><div className="form-grid"><label>Authority<select disabled={isGuardian} value={guardian.authority} onChange={(event) => setGuardian((value) => ({ ...value, authority: event.target.value as GuardianRules['authority'] }))}><option value="none">None</option><option value="shared">Shared</option><option value="delegated">Delegated</option></select></label><label>Guardian account ID<input disabled={isGuardian || guardian.authority === 'none'} value={guardian.guardian_id ?? ''} onChange={(event) => setGuardian((value) => ({ ...value, guardian_id: event.target.value || null }))} /></label></div>{guardian.authority !== 'none' && <div className="choice-grid permission-grid">{(permissions.role_actions.guardian ?? []).map((action) => <Choice key={action} label={ACTION_OPTIONS.find(([value]) => value === action)?.[1] ?? action} disabled={isGuardian} checked={guardian.allowed_actions.includes(action)} onChange={() => setGuardian((value) => ({ ...value, allowed_actions: value.allowed_actions.includes(action) ? value.allowed_actions.filter((item) => item !== action) : [...value.allowed_actions, action] }))} />)}</div>}</fieldset>
      <fieldset><legend>Additional choices</legend><div className="form-grid"><label>Third-party visibility<select value={permissions.third_party_visibility} onChange={(event) => setPermissions((value) => ({ ...value, third_party_visibility: event.target.value as ConsentPermissions['third_party_visibility'] }))}><option value="consented_only">Only people with recorded consent</option><option value="family_reviewed">People reviewed by family</option></select></label><label>After death<select disabled={isGuardian} value={postDeath.mode} onChange={(event) => setPostDeath({ mode: event.target.value as PostDeathPolicy['mode'], beneficiary_user_id: null, retention_days: null })}><option value="keep_private">Keep private</option><option value="transfer_to_guardian">Transfer to guardian</option><option value="delete">Delete</option></select></label>{postDeath.mode === 'transfer_to_guardian' && <label>Beneficiary account ID<input disabled={isGuardian} value={postDeath.beneficiary_user_id ?? ''} onChange={(event) => setPostDeath((value) => ({ ...value, beneficiary_user_id: event.target.value || null }))} required /></label>}{postDeath.mode === 'delete' && <label>Retention days<input disabled={isGuardian} type="number" min="0" max="3650" value={postDeath.retention_days ?? ''} onChange={(event) => setPostDeath((value) => ({ ...value, retention_days: event.target.value === '' ? null : Number(event.target.value) }))} /></label>}<label>Witness<input value={witness} onChange={(event) => setWitness(event.target.value)} /></label></div><Choice label="Allow anonymized data for model training" checked={training} disabled={isGuardian} onChange={() => setTraining((value) => !value)} /></fieldset>
      {error && <p className="error" role="alert">{error}</p>}<button className="btn primary" type="submit" disabled={busy}>{busy ? 'Signing...' : 'Sign this version'}</button>
    </form>}
  </div>
}

function Choice({ label, checked, disabled = false, onChange }: { label: string; checked: boolean; disabled?: boolean; onChange: () => void }) { return <label className="choice-row"><input type="checkbox" checked={checked} disabled={disabled} onChange={onChange} /><span>{label}</span></label> }

function ThirdPartyRow({ record, canManage, onAct }: { record: ThirdPartyConsent; canManage: boolean; onAct: (fn: () => Promise<unknown>, message: string) => void }) {
  const [editing, setEditing] = useState(false)
  return <div className="stack"><div className="row"><div className="row-main"><div className="row-title">{record.person_name}<Badge tone={record.consent_given ? 'green' : 'red'}>{record.consent_given ? 'consented' : 'not consented'}</Badge></div><div className="row-sub">{[record.contact, record.person_id ? `Person ${record.person_id}` : null, new Date(record.created_at).toLocaleDateString()].filter(Boolean).join(' · ')}</div>{record.notes && <p className="muted">{record.notes}</p>}</div>{canManage && <div className="row-actions"><button type="button" className="btn" onClick={() => setEditing((value) => !value)}>{editing ? 'Cancel' : 'Edit'}</button><button type="button" className="btn danger" onClick={() => window.confirm(`Delete the consent record for ${record.person_name}?`) && onAct(() => api.deleteThirdParty(record.id), 'Consent record deleted.')}>Delete</button></div>}</div>{editing && <ThirdPartyForm record={record} onSave={(update) => { setEditing(false); onAct(() => api.updateThirdParty(record.id, update), 'Consent record updated.') }} />}</div>
}

function ThirdPartyForm({ record, onSave }: { record: ThirdPartyConsent; onSave: (update: { person_name: string; contact: string | null; consent_given: boolean; notes: string | null }) => void }) {
  const [name, setName] = useState(record.person_name); const [contact, setContact] = useState(record.contact ?? ''); const [consented, setConsented] = useState(record.consent_given); const [notes, setNotes] = useState(record.notes ?? '')
  return <form className="panel form" onSubmit={(event) => { event.preventDefault(); onSave({ person_name: name, contact: contact || null, consent_given: consented, notes: notes || null }) }}><label>Name<input value={name} onChange={(event) => setName(event.target.value)} required /></label><label>Contact<input value={contact} onChange={(event) => setContact(event.target.value)} /></label><Choice label="Consent given" checked={consented} onChange={() => setConsented((value) => !value)} /><label>Notes<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label><button type="submit" className="btn primary">Save record</button></form>
}

function AddThirdParty({ onDone }: { onDone: () => void }) {
  const [show, setShow] = useState(false); const [name, setName] = useState(''); const [contact, setContact] = useState(''); const [consented, setConsented] = useState(false); const [notes, setNotes] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null)
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(null); try { await api.createThirdParty({ person_name: name, contact: contact || null, consent_given: consented, notes: notes || null }); setName(''); setContact(''); setConsented(false); setNotes(''); setShow(false); onDone() } catch (caught) { setError(caught instanceof ApiError ? caught.message : 'The record could not be added.') } finally { setBusy(false) } }
  return <div className="panel"><div className="page-head"><h3>Add a person</h3><button type="button" className="btn primary" onClick={() => setShow((value) => !value)}><Icon name="plus" size={16} />{show ? 'Cancel' : 'Add consent record'}</button></div>{show && <form className="form" onSubmit={submit}><label>Person name<input value={name} onChange={(event) => setName(event.target.value)} required /></label><label>Contact<input value={contact} onChange={(event) => setContact(event.target.value)} /></label><Choice label="Consent given" checked={consented} onChange={() => setConsented((value) => !value)} /><label>Notes<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>{error && <p className="error" role="alert">{error}</p>}<button type="submit" className="btn primary" disabled={busy}>{busy ? 'Adding...' : 'Add record'}</button></form>}</div>
}
