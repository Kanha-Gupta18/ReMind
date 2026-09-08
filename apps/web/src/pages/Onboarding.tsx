import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, api, PATIENT_PROFILE_UPDATED_EVENT } from '../api/client'
import type { AccessibilityProfile, PatientProfileCreate } from '../api/types'
import { useApiData } from '../api/useApiData'
import { useAuth } from '../auth/AuthContext'

const DEFAULT_ACCESSIBILITY: AccessibilityProfile = {
  text_size: 'standard',
  high_contrast: false,
  reduced_motion: false,
  narration_auto_start: false,
  simplified_navigation: true,
}

export function Onboarding() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const directives = useApiData(() => api.consentDirectives(), [user?.id])
  const profile = useApiData(() => api.patientProfile(), [user?.id])
  const [preferredName, setPreferredName] = useState(user?.full_name ?? '')
  const [language, setLanguage] = useState('en-IN')
  const [birthDate, setBirthDate] = useState('')
  const [accessibility, setAccessibility] = useState(DEFAULT_ACCESSIBILITY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!profile.data) return
    setPreferredName(profile.data.preferred_name)
    setLanguage(profile.data.preferred_language)
    setBirthDate(profile.data.date_of_birth ?? '')
    setAccessibility({ ...DEFAULT_ACCESSIBILITY, ...profile.data.accessibility_profile })
  }, [profile.data])

  if (user?.role !== 'patient') {
    return <section className="empty-state"><h1>Patient setup</h1><p>Only the patient can sign the first consent directive.</p></section>
  }
  if (directives.data && directives.data.count > 0) {
    return <section className="onboarding-complete">
      <p className="setup-status">Setup complete</p>
      <h1>Your ReMind profile is ready.</h1>
      <p>You can adjust your profile or sign a new consent version whenever your choices change.</p>
      <div className="form-actions"><Link className="btn primary" to="/profile">Review profile</Link><Link className="btn" to="/consent">Review consent</Link></div>
    </section>
  }

  function updateAccessibility(key: keyof AccessibilityProfile, value: boolean | AccessibilityProfile['text_size']) {
    setAccessibility((current) => ({ ...current, [key]: value }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null)
    const patientProfile: PatientProfileCreate = {
      preferred_name: preferredName,
      preferred_language: language,
      accessibility_profile: accessibility,
      date_of_birth: birthDate || null,
      diagnosis: null,
      diagnosis_date: null,
      cognition_level: null,
      safety_level: 'NORMAL',
      status: 'active',
    }
    try {
      await api.completeOnboarding({
        profile: patientProfile,
        consent: {
          permissions: { allowed_data_sources: [], role_actions: {}, third_party_visibility: 'consented_only' },
          restrictions: { prohibited_data_categories: [], blocked_person_ids: [] },
          guardian_rules: { guardian_id: null, authority: 'none', allowed_actions: [] },
          training_opt_in: false,
          post_death_policy: { mode: 'keep_private', beneficiary_user_id: null, retention_days: null },
        },
      })
      window.dispatchEvent(new Event(PATIENT_PROFILE_UPDATED_EVENT))
      navigate('/consent')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Setup could not be completed.')
    } finally { setBusy(false) }
  }

  return <section className="onboarding-page">
    <div className="onboarding-intro"><h1>Set up ReMind around you.</h1><p>Start with how you want the app to address and support you. Your archive begins private.</p></div>
    {(directives.loading || profile.loading) && <p className="muted">Loading your setup...</p>}
    <form className="onboarding-form" onSubmit={submit}>
      <fieldset><legend>About you</legend><div className="form-grid">
        <label>Preferred name<input value={preferredName} onChange={(event) => setPreferredName(event.target.value)} required /></label>
        <label>Preferred language<input value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="en-IN" required /></label>
        <label>Date of birth<input type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
      </div></fieldset>
      <fieldset><legend>Make the experience comfortable</legend><div className="accessibility-options">
        <label>Text size<select value={accessibility.text_size} onChange={(event) => updateAccessibility('text_size', event.target.value as AccessibilityProfile['text_size'])}><option value="standard">Standard</option><option value="large">Large</option><option value="extra_large">Extra large</option></select></label>
        {([['high_contrast', 'Use higher contrast'], ['reduced_motion', 'Reduce motion'], ['narration_auto_start', 'Start narration automatically'], ['simplified_navigation', 'Use simplified navigation']] as const).map(([key, label]) => <label className="choice-row" key={key}><input type="checkbox" checked={accessibility[key]} onChange={(event) => updateAccessibility(key, event.target.checked)} /><span>{label}</span></label>)}
      </div></fieldset>
      <div className="privacy-start"><strong>Private by default</strong><p>No family, caregiver, clinician, source type, or model-training permission is enabled by this first signature. The next screen lets you review and change each choice.</p></div>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" className="btn primary" disabled={busy}>{busy ? 'Saving setup...' : 'Complete private setup'}</button>
    </form>
  </section>
}
