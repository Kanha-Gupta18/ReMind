# Roadmap

## Milestone 0 — Trust boundary hardening

- [x] Enforce `APPROVED` state on every patient-facing memory endpoint.
- [x] Limit patient identity output to family-confirmed face and person records.
- [x] Filter patient conversation and graph-derived traversal to confirmed,
  non-disputed facts.
- [x] Remove caller-controlled server file paths and constrain all source reads to managed storage.
- [x] Turn consent directives into authorization policies across upload, access, retrieval, and delivery.
- Correct memory revision promotion and rejection behavior.
- Implement source deletion propagation and regression tests.
- Add adversarial tests for the product's core invariant.

## Milestone 1 — Trusted family memory vault

- [x] Patient profile and onboarding workflows.
- [x] Revocable multi-patient relationships and server-backed login sessions.
- Secure image upload and manual people/event tagging.
- Source provenance and family review workspace.
- Accessible patient home, photo-led memory cards, timeline, and narration.
- Versioned corrections, sensitivity controls, export, and deletion.
- Grounded conversation over approved memories only.
- Reproducible local environment and deployment baseline.

## Product-wide experience and visual system

- Replace prototype styling after the family workflow is functionally complete.
- Establish shared typography, color, spacing, navigation, form, feedback, and
  content-state patterns across role experiences.
- Add responsive layouts and purposeful interaction feedback with reduced-motion
  behavior.
- Visually verify family, patient, caregiver, clinician, and administrator paths
  at representative desktop and mobile sizes.
- Keep patient-specific accessibility and cognitive-safety validation as its own
  following section.

## Milestone 2 — AI-assisted reconstruction

- Real OCR and image metadata extraction.
- Face clustering with family-confirmation policy.
- Entity, date, location, and contradiction extraction.
- Calibrated confidence scoring and evidence explanations.
- Provider-isolated AI draft generation with complete model governance metadata.
- Gold-standard evaluation sets and demographic/image-quality testing.

## Milestone 3 — Multimodal expansion

- WhatsApp and SMS imports.
- Voice notes and interview transcription.
- Home-video processing.
- Location-history imports.
- Cross-modal event linking and semantic search.

## Milestone 4 — Caregiver safety layer

- Configurable distress and sensitive-memory workflows.
- Immediate neutral-content transition after emergency stop.
- Caregiver annotations, escalation policies, and engagement summaries.
- Safety monitoring and restricted-content leak tests.

## Milestone 5 — Validated clinical/research deployment

- Consent-scoped clinician experience.
- Approved reports and longitudinal engagement views.
- Institution isolation, research protocols, and ethics workflows.
- Clinical validation before making any clinical claim.
