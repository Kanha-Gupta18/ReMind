# Contributing

ReMind handles unusually sensitive product behavior. Correctness, provenance, and safe failure are more important than feature volume.

## Before making a change

1. Read the product principles in the README and `docs/PRODUCT.md`.
2. State which user and trust boundary the change affects.
3. Keep the change narrowly scoped.
4. Add or update tests for the intended behavior and unsafe alternatives.

## Development checks

Backend:

```powershell
cd services/api
.\venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd apps/web
npm run build
```

## Safety-sensitive changes

Changes involving memory delivery, people, relationships, consent, deletion, visibility, or conversation should test at least:

- Unreviewed content is not patient-visible.
- Disputed and restricted content is not patient-visible.
- Unknown or probable identities are not stated as confirmed.
- Cross-patient access fails.
- Deleted sources cannot influence retrieval.
- Consent changes take effect on subsequent access.
- Unsupported questions produce an honest fallback.

## Pull requests

Describe what changed, why it is safe, how it was tested, and any remaining limitations. Do not commit `.env` files, database contents, uploads, logs, tokens, or real personal data.
