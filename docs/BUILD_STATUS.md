# Build progress

Sections are complete only after their acceptance checks pass. This file records
implementation status separately from planned functionality.

| Section | Target | Status |
| --- | --- | --- |
| 1 | Development baseline and test reliability | Complete: fresh installs, web build, migrations, schema drift check, 98 API tests |
| 2 | Immediate access and patient-delivery flaws | Complete: patient delivery is fail-closed across content routes; 121 API tests |
| 3 | Accounts, patient profiles, and consent | Planned |
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

Consent policy enforcement remains Section 3. Revision promotion, source deletion
propagation, and real extraction remain assigned to Sections 4, 5, and 12.
