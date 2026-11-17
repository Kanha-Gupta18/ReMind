# ReMind hackathon release

Planning date: November 17, 2026. Presentation: November 21 or 22, pending confirmation.
Budget: free hosting and free AI services only. No paid subscriptions or paid API usage.

## Event fit and confirmed public schedule

Event: Agentic AI Hackathon 2026, listed by AMSE with Ulster University as organizer.
Source: https://theamse.org/hackathon/AgenticAIHackathon2026

- Proposed track: Agentic AI for Healthcare & Human Well-being.
- Round I idea/PPT deadline: November 16, 2026, 10:00 PM.
- Round I results: November 19, 2026, 10:00 PM.
- Round II online presentation: November 21-22, 2026.
- Round II results: November 28, 2026, 10:00 PM.
- The page does not specify a timezone for these deadlines.
- The user confirmed Round I PPT submission. Eligibility of pre-existing work, detailed judging
  criteria, presentation length, and assigned slot remain unverified. The linked
  participant rules require a readable copy; the web reader returned only the
  Google Docs JavaScript shell.

The proposed demo should show agent behavior rather than only generation:
inspect the uploaded photo, retrieve authorized supporting context, identify
missing information, ask for family clarification, and prepare an evidence-linked
candidate. Bound the tool loop and record the actual tool calls, decisions,
provider/model, and failures. Human approval remains mandatory before patient
delivery. Identities, dates, relationships, and places must not be invented from
appearance or model confidence. This is a release requirement, not an implemented
capability.

## Release goal

Deliver a deployed, working demonstration of one family-to-patient memory workflow:

1. A family member uploads a synthetic family photograph.
2. Real processing proposes only supported observations and explicitly records unknowns.
3. A family reviewer confirms people, context, evidence, and sensitivity labels.
4. Approval publishes the verified revision to the patient experience.
5. The patient explores the photograph and asks a question answered from approved evidence.
6. A consent change or stop control demonstrates the trust boundary.

The differentiator is visible human verification and evidence provenance. Simulator
output must never be described as real AI. The full product roadmap remains active;
this release completes a smaller set of capabilities rather than declaring the whole
platform complete. Use synthetic data and clearly identify the demonstration accounts.

## Ordered checkpoints

Pause after each checkpoint for user testing and debugging before starting the next.
Dates are working targets, not claims of completion.

| Checkpoint | Target | Work | Acceptance |
| --- | --- | --- | --- |
| H1 | November 17 | Confirm hackathon constraints, inspect current branch and PR, establish deployment configuration, private persistent storage, environment validation, and readiness checks | A preview survives a restart without losing its source files; secrets stay server-side; authenticated source access remains enforced |
| H2 | November 18 | Build one real photo-to-draft processing path with explicit evidence, unknowns, provider attribution, quota/error handling, and mandatory review | An unseen photograph produces a traceable draft; absent identity/date information stays unknown; AI cannot publish |
| H3 | November 19 | Redesign the shared shell, family upload/review workflow, patient timeline/detail, and grounded photo conversation | A presenter can complete the central workflow without API tools; desktop, mobile, keyboard, and reduced-motion checks pass |
| H4 | November 20 | Deploy the release, seed a coherent synthetic story, verify role/consent isolation, correction and deletion behavior used by the demo, and restart persistence | Public HTTPS demo passes the complete scripted walkthrough; no local server is required |
| H5 | Before presentation | Rehearse, test from a separate browser/device, prepare screenshots and a recorded backup, freeze the release | The live workflow fits the confirmed presentation limit and the backup is explicitly identified as recorded |

Do not add a second import format, clinician workflow, or graph-database migration
unless required by the hackathon or the demonstrated workflow. Unfinished features
stay disclosed and cannot be presented as delivered capabilities.

## Design brief

ReMind is an operating application for patients and families. Photography and familiar
context lead; controls support recognition and clear decisions. Preserve the product's
calm character while replacing crowded navigation and undifferentiated form layouts.

- Family: persistent task navigation, visible upload/review progress, photograph next
  to evidence and proposed facts, explicit review decisions and publication state.
- Patient: fewer choices, large photo-led memories, readable names and context,
  simple next/back controls, an obvious stop action, and understandable uncertainty.
- Shared: one token/component system, visible focus, sufficient contrast, responsive
  layouts, useful loading/error/empty states, and short purposeful transitions.
- Product truth: no clinical efficacy, adoption, accuracy, or user-count claims
  without supporting evidence. No invented faces, dates, identities, or provenance.

Use Emil Design Engineering for interaction details and purposeful motion,
Karpathy Guidelines for focused implementation and tests, Humanizer for prose,
and Impeccable for application design/accessibility. Design Taste applies to the
entry experience and visual redesign within its scope, not as a marketing layout
for patient tasks. ECC Product Lens supplies release prioritization.

## Free service candidates and constraints

Proposed: Render static frontend and FastAPI service, Supabase PostgreSQL and a
private Storage bucket, and a provider/model with an available free AI quota.
Provider/model selection requires an actual quota and deployment smoke test.
Keep existing SQLAlchemy, Alembic, PostgreSQL, and JWT architecture.

- Render free web services sleep after inactivity and lose local runtime files.
  Never store demo uploads only on that filesystem. Open and rehearse the real
  demo shortly before presenting; do not bypass provider usage rules.
- Supabase currently provides a free database and file-storage allowance. Private
  files must pass API authorization; do not expose service credentials or make the
  source bucket public.
- Free AI quotas can fail or change. Handle unavailability honestly and retain
  previously reviewed examples for exploration; never substitute simulator output
  silently. Any free provider's data-use terms must fit synthetic demo content.
- Real patient use, clinical validation, and full operational readiness are separate
  milestones. A hackathon deployment does not complete roadmap Section 14 or 15.

Sources checked November 17, 2026:

- https://render.com/docs/free
- https://supabase.com/pricing
- https://ai.google.dev/gemini-api/docs/pricing

## Decisions still needed

- Participant rules, required technologies,
  judging criteria, assigned presentation slot and duration, and whether judges
  need independent demo access.
- User access to the selected free hosting/storage accounts and an eligible free
  AI API key. Set credentials through provider secret settings, never in Git.
- Visual references and final surface direction before broad UI implementation.

## Status

Planning checklist recorded. Round I PPT submission is confirmed. Both hosting
accounts still need to be created by the user. H1 implementation is on
`codex/h1-deployment-foundation`; real cloud persistence is not yet verified.
Existing Section 4 consent fixes were locally tested
and pushed in commit `9de532f`; PR #2 was opened with passing CI in the previous
session. Recheck its live state before basing release branches or merges on it.
H1 adds private source storage, bounded uploads, failed-transaction cleanup,
production settings validation, readiness checks, an API container, a free Render
blueprint, and a deployment guide. Cloud persistence is not yet verified. H2 has
not started. Follow docs/DEPLOYMENT.md to complete H1's cloud acceptance test.
