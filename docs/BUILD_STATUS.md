# Build progress

Sections are complete only after their acceptance checks pass. This file records
implementation status separately from planned functionality.

| Section | Target | Status |
| --- | --- | --- |
| 1 | Development baseline and test reliability | Complete: fresh installs, web build, migrations, schema drift check, 98 API tests |
| 2 | Immediate access and patient-delivery flaws | In progress |
| 3 | Accounts, patient profiles, and consent | Planned |
| 4 | Canonical memory data and revisions | Planned |
| 5 | Corrections, deletion, and export | Planned |
| 6 | Trusted uploads and processing jobs | Planned |
| 7 | Family contribution and verification workspace | Planned |
| 8 | Patient experience and accessibility | Planned |
| 9 | Caregiver assistance and emotional safety | Planned |
| 10 | Grounded conversation and retrieval | Planned |
| 11 | Real AI-assisted reconstruction | Planned; provider decision required |
| 12 | Multimodal imports | Planned |
| 13 | Deployment and controlled pilot readiness | Planned; deployment decisions required |
| 14 | Clinical and research capabilities | Planned; external validation required |

## Acceptance requirements

The product requirements are summarized in PRODUCT.md and ARCHITECTURE.md.
ROADMAP.md tracks missing functionality. The original specification defines
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
