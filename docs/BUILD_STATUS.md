# Build progress

Sections are complete only after their acceptance checks pass. This file records
implementation status separately from planned functionality.

| Section | Target | Status |
| --- | --- | --- |
| 1 | Development baseline and test reliability | Complete: fresh installs, web build, migrations, schema drift check, 98 API tests |
| 2 | Immediate access and patient-delivery flaws | Complete: patient delivery is fail-closed across content routes; 121 API tests |
| 3 | Accounts, patient profiles, and consent | Complete: revocable relationships, server-backed sessions, onboarding, profiles, and enforced versioned consent; 135 API tests |
| 4 | Canonical memory data and revisions | Planned |
| 5 | Corrections, deletion, and export | Planned |
| 6 | Trusted uploads and processing jobs | Planned |
| 7 | Family contribution and verification workspace | Planned |
| 8 | Product-wide experience and visual design system | Planned |
| 9 | Patient experience and accessibility | Planned |
| 10 | Caregiver assistance and emotional safety | Planned |
| 11 | Grounded conversation and retrieval | Planned |
| 12 | Real AI-assisted reconstruction | Planned; provider decision required |
| 13 | Multimodal imports | Planned |
| 14 | Deployment and controlled pilot readiness | Planned; deployment decisions required |
| 15 | Clinical and research capabilities | Planned; external validation required |

## Acceptance requirements

The implementation order is defined in BUILD_PLAN.md. Product requirements are
summarized in PRODUCT.md and ARCHITECTURE.md. ROADMAP.md tracks missing functionality. The original specification defines
the primary invariant: every patient-facing autobiographical claim needs
traceable evidence and appropriate review. Approval, consent, sensitivity,
identity confirmation, and deletion must apply across all delivery paths.

Section 1 must demonstrate a fresh dependency install, frontend build, database
migration, and passing API suite with no access to development tables or files.
Section 2 must add regression coverage for alternate content routes, arbitrary
filesystem paths, uncertain identities, and missing patient links.

## Section 1 verification

- Fresh Python environment installed from requirements.txt; 98 tests passed.
- Tests migrate a unique generated PostgreSQL schema and check model drift.
- Test storage is always generated; application STORAGE_DIR is never reused.
- Fresh npm lockfile install and TypeScript/Vite production build passed.
- CI runs on section branches as well as main and pull requests.
- Current Starlette warns that httpx support is deprecated in favor of httpx2;
  the earlier review describing httpx2 as a typo was incorrect. Compatibility
  currently passes, but dependency locking/upgrades should track this warning.

## Section 2 verification

Branch: `codex/02-patient-access`.

- Patient memory delivery now requires approved status, patient or shared
  visibility, and the existing safety policy. The same decision applies to
  detail, timeline, evidence, source, engagement, graph-derived, and conversation
  reads.
- Patients cannot read revision history. Evidence shown to a patient must be
  accepted and cannot refer to a deleted, missing, or different patient's source.
- A source becomes patient-readable only when accepted evidence connects it to a
  memory the patient may currently receive. Patient source responses omit storage,
  uploader, checksum, extraction, pipeline, and family context fields.
- Patient people and face results require family-confirmed identities. Patient
  graph-derived relations require confirmed, undisputed edges and hide internal
  source, consent, and sensitive-category nodes.
- Conversation replies use the same delivery checks. Direct responses hide tool
  parameters and results, stored history omits tool records, and prior answers are
  replaced if their current source or review state no longer supports them.
- Unlinked non-administrator accounts receive a 403 response instead of an
  unrestricted scope. Source creation rejects caller-selected server paths, and
  file delivery is confined to the source's managed patient directory.
- All 121 API tests passed, including 23 focused access regressions. TypeScript
  checking and the Vite production build passed. `git diff --check` passed with
  Windows line-ending notices only.

Revision promotion, source deletion propagation, and real extraction remain
assigned to Sections 4, 5, and 12.

## Section 3 verification

Branch: `codex/03-accounts-consent`.

- Login sessions are stored server-side, expire after inactivity or their absolute
  lifetime, rotate refresh tokens, reject refresh-token replay, and are revoked on
  logout, password changes, role changes, or account deactivation.
- Patient access is represented by revocable relationship records. An account can
  support more than one patient, and removing a relationship takes effect on the
  next request. Administrators can manage accounts but cannot read patient content.
- Patients can complete first-time onboarding, maintain their care and
  accessibility profile, and grant or revoke family relationships. All profile and
  relationship routes check both the relationship and the current consent policy.
- Consent directives are immutable versions with typed source permissions, role
  permissions, restrictions, guardian authority, third-party visibility, training
  preference, and post-death instructions. Guardians may only exercise explicitly
  delegated authority and may only make a directive more restrictive.
- Consent is enforced across memories, sources, people, graph retrieval,
  conversations, timeline delivery, safety information, and notifications.
  Previously issued notifications also disappear when their underlying permission
  is withdrawn.
- The web app now refreshes sessions safely, supports explicit patient selection,
  and provides onboarding, profile, relationship, and structured consent screens.
- All 135 API tests passed. TypeScript checking, the Vite production build,
  `git diff --check`, and the UI mechanical-quality detector passed.

Canonical revision selection remains Section 4. Correction and deletion
propagation, export, production identity hardening such as MFA, and the full visual
redesign remain assigned to Sections 5, 8, and 14 as defined in the build plan.
