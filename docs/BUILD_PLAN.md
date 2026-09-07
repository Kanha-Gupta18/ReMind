# ReMind build order

Each section includes implementation, relevant tests, documentation, and a
reviewable GitHub update. Work pauses after every section so the result can be
tested and debugged before the next section starts.

| Order | Section | Work and completion checkpoint |
| --- | --- | --- |
| 1 | Development baseline and test reliability | Verify fresh installation, migrations, CI, dependencies, and isolated tests. A fresh checkout builds and runs its checks without undocumented local setup. |
| 2 | Immediate access and patient-delivery flaws | Close arbitrary file access and enforce review state and visibility across memory, evidence, revision, source, people, graph, and conversation paths. Tests prove hidden or invalid content cannot be retrieved through another route. |
| 3 | Accounts, patient profiles, and consent | Complete onboarding, profiles, family relationships, sessions, and enforceable consent. Every permitted action requires an authorized relationship and applicable consent. |
| 4 | Canonical memory data and revisions | Establish structured people, places, events, dates, evidence, and review records. Candidate edits, decisions, approved revisions, and history remain accurate. |
| 5 | Corrections, deletion, and export | Propagate corrections, invalidate derivatives of deleted sources, remove file access, reassess memories, and provide authorized export. Removed information cannot appear through another route. |
| 6 | Trusted uploads and processing jobs | Add secure photo ingestion, validation, metadata, duplicate handling, managed storage, background jobs, progress, retries, and recovery. An upload reaches a traceable reviewable result. |
| 7 | Family contribution and verification workspace | Make tagging, source linking, memory creation, corrections, sensitivity controls, review, and dispute handling usable. A family can complete the upload-to-publish workflow. |
| 8 | Product-wide experience and visual design system | Replace the prototype styling with a coherent, role-aware interface system. Establish typography, color, spacing, components, navigation, states, responsive behavior, restrained motion, and human interface copy across the application. Desktop and mobile visual checks pass for every role, with consistent loading, empty, error, focus, and reduced-motion states. |
| 9 | Patient experience and accessibility | Build the simplified home, photo-led memory cards, people and places, uncertainty language, narration, and easy navigation. Validate keyboard and screen-reader use, text scaling, responsive layouts, and localization foundations. |
| 10 | Caregiver assistance and emotional safety | Complete assisted sessions, immediate stop controls, narration cancellation, neutral transitions, linked safety events, notifications, and engagement summaries. Caregivers can stop distressing interactions and identify the triggering content. |
| 11 | Grounded conversation and retrieval | Replace brittle routing with controlled retrieval. Apply consent, review, identity, sensitivity, and deletion policies to tools and stored conversation views. Answers cite evidence, admit unknowns, and resist leading prompts. |
| 12 | Real AI-assisted reconstruction | Add real OCR, vision, face clustering, entity, date, and place extraction, followed by restrained draft generation. Provider, model, and prompt versions are recorded; no AI output publishes itself. |
| 13 | Multimodal imports | Add message imports, then transcription, video, location history, and cross-source event linking. Every format passes ingestion, review, correction, provenance, and deletion tests before the next is enabled. |
| 14 | Deployment and controlled pilot readiness | Complete environment configuration, encrypted storage, secrets, monitoring, rate limits, backups, retention, operational documentation, and full workflow tests. A documented readiness review precedes any pilot. |
| 15 | Clinical and research capabilities | Add consent-scoped clinician reports, longitudinal views, institution boundaries, and research workflows after product validation. Software checks and external clinical and ethical review must pass before clinical use or claims. |

## Section checkpoint report

At the end of every section, report its purpose, findings, code and behavior
changes, verification results, known limitations, and GitHub branch or commit.
Include exact instructions for running the application, reaching the feature,
choosing the appropriate role, reproducing the expected behavior, and reporting
debugging findings. Do not start the next section until the user approves it.

## Design implementation rules

Section 8 is a product redesign, not a cosmetic pass. Preserve working routes,
field names, consent language, and task flows unless a reviewed usability issue
requires a change. Use one shared token and component foundation, with layouts
adapted to each role. Family and professional workspaces prioritize clear task
completion. Patient surfaces prioritize recognition, calm presentation, large
targets, simple choices, and predictable navigation.

Motion must explain feedback or state changes, remain brief, and respect reduced
motion. Visual verification covers representative desktop and mobile widths,
light and dark modes if both are supported, keyboard focus, contrast, content
overflow, and loading, empty, success, and failure states. Section 9 then applies
the additional accessibility and cognitive-safety requirements specific to the
patient experience.

## Working defaults

- Keep the current React, FastAPI, and PostgreSQL architecture unless evidence
  shows a split is necessary.
- Preserve existing data through migrations and use synthetic isolated test data.
- Put security fixes and regression tests in the section that discovers them.
- Choose paid providers, hosting region, supported languages, and pilot details
  when their sections are ready, with concrete options for review.
- Treat clinical validation as an external milestone, not a software test result.
