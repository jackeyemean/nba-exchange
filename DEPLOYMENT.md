# Hoop Exchange – Step-by-Step Deployment Guide

Deploy: **Frontend** (Vercel) → **API** (Fly.io) → **Database + Auth** (Supabase) → **Market automation** (GitHub Actions)

---

## Prerequisites

- GitHub repo with your code pushed
- Supabase project (you already have one)
- Google Cloud OAuth credentials
- Accounts: Vercel, Fly.io, Supabase (all free tiers work)

---

## Part 1: Supabase (Database + Auth)

### 1.1 Get your production database URL

**You don’t change anything in Supabase.** You only copy a connection string and edit it locally (replace password, add SSL).

**Step 1: Open the Connect panel**

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Click your project
3. Click the **Connect** button (usually top right of the project view, or in the main header)
4. A panel or dropdown opens with connection options

**Step 2: Get your database password**

- If you already have it, skip this.
- If not: **Project Settings** (gear in left sidebar) → **Database** → **Database password** → **Reset database password**
- Copy the new password and store it somewhere safe

**Step 3: Copy the connection string**

In the Connect panel, look for:

- **Connection pooling** or tabs like **Session** / **Transaction**
- Choose **Transaction** (port 6543) – best for Fly.io and GitHub Actions
- Copy the **URI** string. It will look like:
  ```
  postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
  ```
  (Supabase may show `[YOUR-PASSWORD]` as a placeholder.)

**Step 4: Edit the string locally (not in Supabase)**

1. Paste the string into a text editor
2. Replace `[YOUR-PASSWORD]` with your actual database password
3. Add `?sslmode=require` at the very end (Supabase doesn’t add this; you do it for secure connections):
   ```
   postgresql://postgres.xxx:YourActualPassword@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```
4. Save this as `DATABASE_URL` – use it for the API, engine, and GitHub Actions

**If the UI looks different**

- Look for **Connect**, **Database**, or **Connection string**
- Or go directly: **Project Settings** (gear in left sidebar) → **Database** → scroll to **Connection string** or **Connection info**
- Use the **Transaction** or **URI** option (port 6543)
- Direct link to Database settings:  
  `https://supabase.com/dashboard/project/<your-project-id>/settings/database`  
  (Your project ID is in the Supabase URL when you open a project.)

---

### 1.2 Run migrations on Supabase

You can run migrations with `psql` or via the Supabase SQL Editor.

#### Option A: Using psql (command line)

**Install psql (if needed):**

- **Windows**: Install [PostgreSQL](https://www.postgresql.org/download/windows/) or use `psql` from WSL
- **macOS**: `brew install libpq` then `brew link --force libpq`
- **Or**: Use the Supabase SQL Editor (Option B) – no install needed

**Run migrations:**

```powershell
# PowerShell - set the variable (replace with your actual URL)
$env:DATABASE_URL = "postgresql://postgres.wcpsztakmbrlsaqnslqi:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

# Run each migration (from repo root)
psql $env:DATABASE_URL -f migrations/001_initial_schema.up.sql
psql $env:DATABASE_URL -f migrations/002_game_stats_wl.up.sql
psql $env:DATABASE_URL -f migrations/003_index_history_precision.up.sql
psql $env:DATABASE_URL -f migrations/004_index_ticker_and_types.up.sql
psql $env:DATABASE_URL -f migrations/005_renaissance_ipo_index.up.sql
psql $env:DATABASE_URL -f migrations/006_oauth_users.up.sql
psql $env:DATABASE_URL -f migrations/007_user_username_seq.up.sql
psql $env:DATABASE_URL -f migrations/008_index_trading.up.sql
psql $env:DATABASE_URL -f migrations/009_rookie_trading_restriction.up.sql
```

```bash
# Bash / WSL / macOS
export DATABASE_URL="postgresql://postgres.xxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

psql "$DATABASE_URL" -f migrations/001_initial_schema.up.sql
psql "$DATABASE_URL" -f migrations/002_game_stats_wl.up.sql
psql "$DATABASE_URL" -f migrations/003_index_history_precision.up.sql
psql "$DATABASE_URL" -f migrations/004_index_ticker_and_types.up.sql
psql "$DATABASE_URL" -f migrations/005_renaissance_ipo_index.up.sql
psql "$DATABASE_URL" -f migrations/006_oauth_users.up.sql
psql "$DATABASE_URL" -f migrations/007_user_username_seq.up.sql
psql "$DATABASE_URL" -f migrations/008_index_trading.up.sql
psql "$DATABASE_URL" -f migrations/009_rookie_trading_restriction.up.sql
```

#### Option B: Using Supabase SQL Editor (no psql needed)

1. In Supabase Dashboard, go to **SQL Editor** (left sidebar)
2. Click **New query**
3. For each migration file:
   - Open the file in your editor (e.g. `migrations/001_initial_schema.up.sql`)
   - Copy the full contents
   - Paste into the SQL Editor
   - Click **Run** (or Ctrl+Enter)
4. Run migrations **in order**: 001 → 002 → 003 → … → 009
5. If you see "relation already exists" or similar, that migration was already applied – move on to the next

**Migration files to run (in order):**

| # | File |
|---|------|
| 1 | `migrations/001_initial_schema.up.sql` |
| 2 | `migrations/002_game_stats_wl.up.sql` |
| 3 | `migrations/003_index_history_precision.up.sql` |
| 4 | `migrations/004_index_ticker_and_types.up.sql` |
| 5 | `migrations/005_renaissance_ipo_index.up.sql` |
| 6 | `migrations/006_oauth_users.up.sql` |
| 7 | `migrations/007_user_username_seq.up.sql` |
| 8 | `migrations/008_index_trading.up.sql` |
| 9 | `migrations/009_rookie_trading_restriction.up.sql` |

**Verify:** After running all migrations, go to **Table Editor** in Supabase. You should see tables like `seasons`, `teams`, `players`, `player_seasons`, `positions`, `wallets`, etc.

### 1.3 Configure Google Auth for production

1. **Supabase Dashboard** → **Authentication** → **URL Configuration**
   - **Site URL**: `https://your-app.vercel.app` (replace with your real Vercel URL after deploy)
   - **Redirect URLs**: Add:
     - `https://your-app.vercel.app/auth/callback`
     - `https://your-app.vercel.app/**`
     - Keep `http://localhost:3000/auth/callback` for local dev

2. **Google Cloud Console** → [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
   - Open your OAuth 2.0 Client ID
   - **Authorized redirect URIs** → Add:
     - `https://wcpsztakmbrlsaqnslqi.supabase.co/auth/v1/callback` (Supabase handles this; verify it matches your project)
   - **Authorized JavaScript origins** → Add:
     - `https://your-app.vercel.app`
     - `https://wcpsztakmbrlsaqnslqi.supabase.co`

3. **Supabase** → **Project Settings** → **API**
   - Copy **JWT Secret** (you already have this as `SUPABASE_JWT_SECRET`)
   - Copy **Project URL** and **anon public** key (you have these)

---

## Part 2: Fly.io (Go API)

### 2.1 Install Fly CLI

```bash
# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# Or: winget install flyctl
```

### 2.2 Create the Fly app

```bash
cd c:\Users\jacky\repos\hoop-exchange

# Login (opens browser)
fly auth login

# Create app from backend directory
fly launch --name hoop-exchange-api --path backend --no-deploy
```

When prompted:
- **App name**: `hoop-exchange-api` (or pick another)
- **Region**: Choose closest to your users (e.g. `iad` for US East)
- **Postgres**: No (you use Supabase)
- **Redis**: No

### 2.3 Set secrets (env vars)

Run from the `backend` directory (where fly.toml lives), or add `-a hoop-exchange-api` to each command:

```powershell
cd backend

fly secrets set DATABASE_URL="postgresql://postgres.xxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
fly secrets set SUPABASE_JWT_SECRET="your-jwt-secret-from-supabase"
fly secrets set SUPABASE_URL="https://wcpsztakmbrlsaqnslqi.supabase.co"
fly secrets set PORT="8080"
fly secrets set STARTING_BALANCE="100000"
fly secrets set SCALING_FACTOR="2.5"
```

**Or** from repo root, specify the app:
```powershell
fly secrets set DATABASE_URL="..." -a hoop-exchange-api
```

**Note:** If your password contains `$`, use single quotes in PowerShell to avoid variable expansion: `'postgresql://...'`

### 2.4 Fix the backend Dockerfile for Fly

The Dockerfile expects to be built from `backend/`. Ensure `fly.toml` exists. Create it if Fly didn’t:

```bash
# If fly.toml wasn't created, create it in backend/
```

Create `backend/fly.toml`:

```toml
# backend/fly.toml
app = "hoop-exchange-api"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

### 2.5 Deploy

```bash
fly deploy --path backend
```

### 2.6 Get your API URL

```bash
fly status
# Or: fly open (opens in browser)
```

Your API URL will be: `https://hoop-exchange-api.fly.dev` (or your app name).

---

## Part 3: Vercel (Frontend)

### 3.1 Import project

1. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**
2. Import your GitHub repo
3. **Root Directory**: set to `web`
4. **Framework Preset**: Next.js (auto-detected)
5. **Build Command**: `npm run build` (default)
6. **Output Directory**: leave default

### 3.2 Environment variables

In **Settings** → **Environment Variables**, add:

| Name | Value | Environment |
|------|-------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://wcpsztakmbrlsaqnslqi.supabase.co` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your anon key from Supabase | Production, Preview |
| `NEXT_PUBLIC_API_URL` | `https://hoop-exchange-api.fly.dev` | Production, Preview |

Use your real Fly.io API URL.

### 3.3 Deploy

Click **Deploy**. After it finishes, copy your Vercel URL (e.g. `https://hoop-exchange-xxx.vercel.app`).

### 3.4 Update Supabase & Google redirect URLs

Go back to **Part 1.3** and replace `your-app.vercel.app` with your actual Vercel URL everywhere.

---

## Part 4: GitHub Actions (Market automation)

### 4.1 Add repository secret

1. GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Name: `DATABASE_URL`
4. Value: Your Supabase database URL (same as Part 1.1)

### 4.2 Create the workflow

Create `.github/workflows/update-market.yml`:

```yaml
name: Daily Market Update

on:
  schedule:
    # 6:00 AM ET = 11:00 UTC (ET is UTC-5, or UTC-4 during DST; 11 UTC covers both)
    - cron: '0 11 * * 1-5'
  workflow_dispatch:  # Allow manual run

jobs:
  update-market:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd engine
          pip install -r requirements.txt

      - name: Run market update
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          cd engine
          python scripts/update_market.py --season 2025-26
```

### 4.3 Push and test

```bash
git add .github/workflows/update-market.yml
git commit -m "Add GitHub Actions market update"
git push
```

Then: **Actions** tab → **Daily Market Update** → **Run workflow** to test.

---

## Part 5: Seed initial data (one-time)

After everything is deployed, run the engine once to populate players, prices, and indexes:

```bash
cd engine
pip install -r requirements.txt

# Use your Supabase DATABASE_URL
export DATABASE_URL="postgresql://postgres.xxx:password@...?sslmode=require"

# Full bootstrap (teams, players, tiers, prices, indexes)
python scripts/restart_simulation.py
```

This can take several minutes. Alternatively, run it from GitHub Actions by adding a one-time workflow or running it locally with the production `DATABASE_URL`.

---

## Checklist

- [ ] Supabase: migrations run, Google Auth URLs updated
- [ ] Fly.io: API deployed, secrets set, URL noted
- [ ] Vercel: frontend deployed, env vars set, URL noted
- [ ] Supabase & Google: redirect URLs use real Vercel URL
- [ ] GitHub Actions: `DATABASE_URL` secret added, workflow created
- [ ] Initial data: `restart_simulation.py` run once

---

## Troubleshooting

**"Connection refused" or "could not connect"**: Use the **pooler** URL (port 6543), not the direct connection (port 5432). Add `?sslmode=require` to the end.

**"Password authentication failed"**: Reset your database password in Supabase → Project Settings → Database → Reset database password. Update your connection string with the new password.

**"relation already exists"**: The migration was already run. Skip it and run the next one.

**psql not found**: Use the Supabase SQL Editor (Option B in 1.2) instead – no local install needed.

**CORS errors**: Backend uses `Access-Control-Allow-Origin: *`. If you want to restrict, update `backend/cmd/api/main.go` to your Vercel domain.

**Auth redirect loop**: Ensure Supabase and Google redirect URIs exactly match your Vercel URL (including `https://`).

**Engine fails in GitHub Actions**: Check `DATABASE_URL` secret. Ensure `?sslmode=require` is present for Supabase.

**API 502**: Fly.io may be scaling from zero. First request can be slow; subsequent ones should be fast.
