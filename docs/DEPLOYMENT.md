# Hackathon preview deployment

This guide deploys the React site and FastAPI service to Render's free plans,
with PostgreSQL and a private source bucket on Supabase's free plan. Use synthetic
content for this demonstration. Real AI processing is a separate H2 checkpoint.

## 1. Supabase project

Create a free Supabase project. Save the database password in a password manager.
Do not add billing or upgrade the plan for this release.

1. In Storage, create a bucket called `remind-sources`. Leave **Public bucket off**.
   Set its upload limit to 6 MB. The API also enforces a 6 MiB limit and rejects
   empty uploads. Content-signature validation and full media processing remain
   later checkpoints; a successful H1 upload is not a claim that media is valid.
2. Do not create anonymous or authenticated-client read/write policies for this
   bucket. ReMind's API authenticates users and authorizes patient access before
   using its server credential. No browser receives a Supabase storage credential,
   public file URL, or signed URL.
3. From project settings, obtain the project HTTPS URL and the legacy `service_role`
   JWT key for the server. Never use the `anon` key for this integration. Keep the
   service role key only in the Render API service's secret environment variables.
4. From Connect, choose the **session pooler** connection string, which supports
   hosts without IPv6. Use the supplied username, host, and port exactly. Change
   `postgresql://` to `postgresql+psycopg://` and add `?sslmode=require` (or
   `&sslmode=require` if it already has a query). URL-encode special characters
   in the database password. Never paste the resulting URL into Git or chat.

## 2. Render blueprint

Connect the repository to Render and create a Blueprint from `render.yaml` on
`codex/h1-deployment-foundation` (or its merged successor). The blueprint declares
one **free** Docker API and one static site. It does not provision a paid database,
disk, or worker. Check the plan summary before applying it.

Configure the API service:

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Supabase session-pooler SQLAlchemy URL from step 1 |
| `JWT_SECRET` | Blueprint-generated random secret; keep it stable across deployments |
| `COOKIE_SECURE` | `true` |
| `STORAGE_BACKEND` | `supabase` |
| `SUPABASE_URL` | Project HTTPS origin, with no path |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only legacy service role JWT |
| `SUPABASE_STORAGE_BUCKET` | `remind-sources` |
| `CORS_ORIGINS` | JSON array containing the exact web origin, such as `["https://your-web.onrender.com"]` |

Configure the static site:

- `VITE_API_URL`: the exact API HTTPS origin, without a trailing slash.
- `NODE_VERSION`: `22` (provided by the blueprint).

The browser's Vite variables are public. Put no passwords or keys in variables
starting with `VITE_`. Rebuild the static site after changing its API URL.

Render may need the two service URLs before CORS and API URL can be finalized.
Create the services, set those values, and redeploy. A correctly configured API
runs Alembic migrations before Uvicorn starts. A failed migration prevents startup.
This startup migration strategy is for the single API instance in this blueprint;
do not scale it horizontally without a separate serialized migration step.

`/health` checks database connectivity. `/ready` returns HTTP 200 only when the
database, migration head, and private bucket check pass. Failures return HTTP 503
with generic component states, without provider responses, credentials, or paths.
Render uses `/ready` as the deployment health check.

## 3. Check the cloud preview

H1 is not fully verified until this check runs on real free-service accounts:

1. Confirm `/ready` returns `ready` for all checks.
2. Provision synthetic patient/family accounts with the existing onboarding and
   relationship setup. Do not add universal public demo credentials to this repo.
   H1 does not add a public registration flow or automatic demo account seed.
3. Sign in as the authorized family contributor and upload a small synthetic photo
   through Sources. Record its source ID and checksum; download it through ReMind.
4. Confirm an unrelated family's account and an unauthenticated browser cannot
   download it. An unreviewed source must remain unavailable to the patient.
5. Restart/redeploy only the API service. The same source must download with the
   same checksum afterward, without reuploading. Its bytes live in the private
   Supabase bucket, not the API container filesystem.
6. Temporarily misconfigure the bucket name and confirm `/ready` returns 503;
   restore the name and confirm readiness recovers. Use only this synthetic demo
   project for fault testing. Do not make the bucket public to test this.

## Local verification

Keep `STORAGE_BACKEND=local` and `ENVIRONMENT=development` locally. Existing local
source paths still work; switching backends does not migrate historical local files.
Re-upload synthetic fixtures to a new preview database or plan a controlled file
migration before using any existing dataset. Never copy `.env` into the image.

From `services/api`:

```powershell
.\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Tests always override the storage backend to local. Supabase integration tests use
an in-memory HTTP transport and synthetic credentials, never a live project. They
verify the REST contract, authorization-before-download, persistence from saved
metadata, bucket privacy, provider failures, missing files, and source isolation.
They do not replace the real restart smoke test above.

Optional Docker check from the repository root, with Docker installed:

```powershell
docker build -t remind-api ./services/api
```

## Limits and follow-up work

- Free Render APIs can sleep after inactivity. Rehearse against the deployed site
  shortly before presenting; account for startup delay. Do not bypass host limits.
- Deletion immediately revokes API access. Full dependent-claim invalidation and
  remote-object purge remain roadmap Section 5; H1 only cleans up a newly stored
  object if its upload transaction fails.
- H1 does not migrate existing disk files, implement real AI, add durable processing
  jobs, provision cloud accounts, seed the full demonstration, or complete the
  deployment-security and clinical readiness roadmap.
- No live deployment can be claimed until hosting credentials are configured and
  the real cloud smoke test passes.

Provider references checked November 17, 2026:

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://supabase.com/pricing
- https://supabase.com/docs/guides/storage/uploads/standard-uploads
- https://supabase.com/docs/guides/database/connecting-to-postgres
