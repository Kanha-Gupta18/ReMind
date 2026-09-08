# Architecture

## Current system

```text
React web app
      |
      v
FastAPI REST API
      |
      +-- authentication and patient scoping
      +-- source and reconstruction services
      +-- memory review and timeline services
      +-- people and graph services
      +-- conversation and safety services
      +-- consent, notification, and audit services
      |
      v
PostgreSQL + local development file storage
```

The API is currently a modular monolith. This keeps the prototype simple while preserving service boundaries that can later move to workers or separate services when operational needs justify it.

## Main domains

- **Identity:** users, server-backed login sessions, patient profiles, and
  revocable patient relationship grants.
- **Consent:** immutable directive versions, typed permission policies, delegated
  guardian authority, and third-party consent records.
- **Evidence:** sources, extracted facts, checksums, and provenance.
- **Memory:** memory cards, review lifecycle, revisions, and confidence.
- **Knowledge:** people, face matches, graph nodes, edges, and edge evidence.
- **Delivery:** timeline, conversation, notifications, and engagement.
- **Safety:** sensitivity flags, safety levels, session stops, and events.
- **Governance:** audit records and model metadata.

## Data flow

1. A permitted family user uploads a source.
2. The source is stored and assigned provenance metadata.
3. Processing extracts candidate people, places, dates, text, and other evidence.
4. Reconstruction proposes a draft memory and confidence explanation.
5. A permitted reviewer corrects, approves, rejects, disputes, or restricts it.
6. Patient-facing retrieval applies review, consent, visibility, sensitivity, and deletion gates.
7. The timeline or conversation layer presents only releasable claims.

Steps 2–4 currently use local storage and deterministic simulators rather than production storage and model providers.

## Target infrastructure

Production evolution is expected to add:

- Encrypted S3-compatible object storage.
- A background job queue and dedicated image, audio, video, and text workers.
- PostgreSQL vector search or a dedicated vector store.
- A graph engine only if relational graph queries become inadequate.
- Central secret management, rate limiting, immutable audit retention, and tested backups.
- Structured tracing for API, model, queue, and retrieval operations.

## Architectural rules

- Every patient-specific claim must reference evidence.
- Review state, consent, visibility, deletion, and sensitivity are authorization inputs, not UI-only attributes.
- Every non-patient request for patient data requires an active relationship grant
  and a currently permitted consent action. Administrators are operational actors,
  not patient-content superusers.
- Corrections create new revisions; approved history is never overwritten invisibly.
- Deleting a source invalidates every derivative across evidence, graph, retrieval, and memory layers.
- Model upgrades create new candidates and never silently rewrite approved memories.
- Production data must not be copied into development or test environments.
