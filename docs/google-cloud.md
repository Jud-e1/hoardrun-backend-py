# Hosting the API for $0: Google Cloud Run + Neon

The plan:
- **Google Cloud Run** runs the API container.
- **Neon** holds the Postgres database. Google's own database (Cloud SQL) has no free plan and starts at about $8 a month.

Both have free plans that cover Hoardrun at its current size. Nothing in the repository changes except the website's API address. The [Dockerfile](../Dockerfile) already uses the port Cloud Run gives it.

Checked November 2026. Re-check the two pricing pages before you start, because free plans change:
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Neon free plan limits](https://neon.com/faqs/free-plan-limits-and-quotas)

## What's free, and the limits

| | Free each month | What Hoardrun uses |
|---|---|---|
| **Cloud Run** (request-based billing) | 2 million requests, 180,000 vCPU-seconds (about 50 hours of 1 CPU actually working), 360,000 GiB-seconds | Far less while you're testing and onboarding the first users |
| **Neon Free** | 1 GB storage per project, 100 compute hours per project. It sleeps after 5 minutes idle and **never bills you on the Free plan**; at the limit, writes stop instead. | 1 GB is a lot of rows for an early app |
| **Cloud Build** (makes the container) | A free monthly allowance of build minutes | About 5 minutes per deploy |
| **Artifact Registry** (stores the container) | A small free storage allowance | Keep only the last 2 images (step 9) |

**Google needs a card** to turn on billing, even for the free tier. New accounts also get trial credit. You won't be charged while you stay inside the limits, and the settings below are chosen to keep you there.

**The costs of $0:**
- **Cold starts.** With nothing kept running, the first request after a quiet spell waits about 5 to 10 seconds while Cloud Run starts the API, and Neon wakes the database in under a second. After that it's fast.
- **Hoardrun card approvals.** Stripe gives the API about 2 seconds to approve a card payment, so a cold start would decline it. Before cards go live, keep one instance always running (`--min-instances 1`). That costs a few dollars a month.
- **Emails are handled.** Cloud Run slows the container as soon as it replies, so Hoardrun waits for a request's emails to go out (up to 10 seconds) before replying. Nothing to configure.

## Steps

You do these yourself, because they're your accounts. Never paste keys into chat. Commands run in a terminal opened in `hoardrun-backend-py`.

### 1. Google Cloud account and a spending alert

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project, for example `hoardrun`. Note its **project ID**.
2. Billing → link a billing account (card needed).
3. **Billing → Budgets & alerts → Create budget:** $1 a month, with alerts at 50%, 90% and 100%. A budget only emails you; it doesn't stop spending. The limits in step 7 are what keep the bill at $0.

### 2. The database on Neon

1. Sign up at [neon.com](https://neon.com) (free, no card).
2. Create a project named `hoardrun`, on Postgres 17, in region **AWS US East (N. Virginia)**. That's close to Cloud Run's `us-east1`.
3. From **Connect**, copy two connection strings:
   - **Pooled** (the host contains `-pooler`): the API uses this one.
   - **Direct** (no `-pooler`): migrations use this one.

   Both end in `?sslmode=require`. Keep them in a password manager.

### 3. Set up the tables

Run the migrations once from your computer, against Neon's **direct** address. Put the address in your terminal's environment; don't save it in a file in the repository.

```bash
cd fintech_backend
```

```bash
set MIGRATION_DATABASE_URL=<direct connection string from Neon>
```

```bash
python -m app.database.migrate upgrade
```

```bash
python -m app.database.migrate status
```

`status` should say the database is up to date. (The `set` command is for Windows Command Prompt; in PowerShell use `$env:MIGRATION_DATABASE_URL="..."`.)

### 4. Install the Google Cloud command line

Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), then:

```bash
gcloud init
```

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

### 5. Make the two production keys

Run this twice, once for each key, and keep both in your password manager:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

One is `JWT_SECRET_KEY` (signs sign-in tokens); the other is `DATA_ENCRYPTION_KEY` (encrypts bank tokens). **Never change `DATA_ENCRYPTION_KEY` once real data exists**, or stored bank links can't be read.

### 6. The API's settings file

Create `hoardrun-backend-py/cloudrun.env.yaml` in Notepad. Git and the upload both ignore this file; keep it that way.

```yaml
ENVIRONMENT: "production"
DATABASE_URL: "<pooled connection string from Neon>"
JWT_SECRET_KEY: "<first key from step 5>"
DATA_ENCRYPTION_KEY: "<second key from step 5>"
APP_URL: "https://www.hoardrun.com"
API_URL: "https://placeholder.run.app"
CORS_ORIGINS: '["https://www.hoardrun.com","https://hoardrun.com"]'
WEB_CONCURRENCY: "1"
```

Add the provider keys the same way as you get them. The names are in [hosting.md](hosting.md): Stripe, Plaid, Persona, Resend, Google, Apple, Alpaca, Anthropic.

### 7. Deploy

```bash
gcloud run deploy hoardrun-api --source . --region us-east1 --allow-unauthenticated --env-vars-file cloudrun.env.yaml --memory 512Mi --cpu 1 --min-instances 0 --max-instances 2 --concurrency 40 --timeout 60
```

What these settings do:
- `--source .` builds from the Dockerfile; Google asks to create a storage folder the first time, so answer yes.
- `us-east1` is a region with the lowest prices.
- `--min-instances 0` means nothing runs while no one is using it, which is free.
- `--max-instances 2` caps how far a traffic spike, or an attack, can grow the bill.
- `--allow-unauthenticated` lets the website reach the API. Hoardrun still checks sign-in on every route.

When it finishes, it prints the **Service URL**, for example `https://hoardrun-api-abc123-ue.a.run.app`.

### 8. Tell the API its own address

```bash
gcloud run services update hoardrun-api --region us-east1 --update-env-vars API_URL=<Service URL>
```

Then check it's up:

```bash
curl <Service URL>/health
```

It should answer `"status":"healthy"`. If the deploy fails, read why with:

```bash
gcloud run services logs read hoardrun-api --region us-east1 --limit 50
```

The usual causes:
- a missing `JWT_SECRET_KEY` or `DATA_ENCRYPTION_KEY`
- a wrong `DATABASE_URL`
- skipping step 3: production refuses to start on an empty or old database

### 9. Keep image storage inside the free allowance

Each deploy stores a new container image. Create `cleanup.json`:

```json
[
  {"name": "keep-2", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-rest", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
```

```bash
gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy --location us-east1 --policy cleanup.json
```

### 10. Point the website at the new API

1. In **Vercel → hoardrun → Settings → Environment Variables**, set `NEXT_PUBLIC_API_URL` to `<Service URL>/api/v1` for Production.
2. **Redeploy** the website. The address is built into the site, including its security rules, so the change only takes effect after a redeploy.
3. Sign up on www.hoardrun.com to check everything works end to end.
4. Update every place that calls the API back, to the new address:
   - Stripe and Persona webhooks
   - the Plaid webhook (`PLAID_WEBHOOK_URL`)
   - the Apple Services ID return URL (`<Service URL>/api/v1/auth/apple/callback`)

   Google sign-in returns to the website, so it doesn't change.

### 11. Turn off Render

Once the new API works, delete the suspended Render service, so the old address can't come back with old code.

## Later updates

After each `git push`, run the step 7 command again to deploy the new backend. To change one setting:

```bash
gcloud run services update hoardrun-api --region us-east1 --update-env-vars NAME=value
```

When the app makes money, move secrets to Google's Secret Manager, keep one instance warm for card approvals, and consider moving the database to a paid plan with backups.
