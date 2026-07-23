# Leverage CRM

A lightweight personal CRM for solo outreach — track leads, manage pipeline, send emails, and log activity.

**Stack:** FastAPI + PostgreSQL backend, React 19 + TypeScript + shadcn/ui frontend, served as a single Docker container or via systemd.

---

## Table of Contents

- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
  - [Docker (recommended)](#docker-recommended)
  - [Systemd (bare metal)](#systemd-bare-metal)
- [Email Provider Setup](#email-provider-setup)
- [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

- Python 3.12+, [`uv`](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
- PostgreSQL 15+ running locally **or** a connection string to a remote DB

### Setup

```bash
git clone https://github.com/thewoddlypenguin/crm-v2.git
cd crm-v2
```

Create a `.env` file in the project root (never committed):

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/leveragecrm
JWT_SECRET=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
REGISTRATION_ENABLED=true   # set to false after your account is created
```

Start the dev servers:

```bash
bash start.sh
```

This runs `uv sync` + `bun install` in parallel, then starts:
- **FastAPI** on `$APP_PORT + 100` (default `5273`) with hot reload
- **Vite** on `$APP_PORT` (default `5173`) — proxies `/api` to FastAPI

Open `http://localhost:5173`, register an account, then set `REGISTRATION_ENABLED=false` in `.env` and restart.

### Project structure

```
crm-v2/
├── app.py              # FastAPI app factory + ASGI export
├── auth.py             # JWT creation, bcrypt, get_current_user dependency
├── db.py               # SQLAlchemy engine, SessionLocal, Base
├── models.py           # ORM models (User, Lead, Segment, Activity, EmailSettings, EmailTemplate)
├── routes.py           # All API routes (single APIRouter mounted at /api)
├── business.py         # Domain logic: scoring, status transitions, follow-up scheduling
├── email_service.py    # Email dispatch abstraction (provider stubs + test mode)
├── limiter.py          # Shared slowapi rate-limiter instance
├── seed.py             # Demo data seeder
├── pyproject.toml      # Python dependencies (managed by uv)
├── Dockerfile
├── docker-compose.yml
├── leverage-crm.service  # systemd unit file
└── src/                # React frontend (Vite + TypeScript + shadcn/ui)
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string — `postgresql://user:pass@host:5432/dbname` |
| `JWT_SECRET` | Random hex secret for signing JWTs. **App refuses to start if unset.** Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |

### Auth & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `REGISTRATION_ENABLED` | `true` | Set to `false` after creating your account to close public registration |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins. Set to your domain in production: `https://crm.example.com` |

### Email (optional — set when wiring a real provider)

| Variable | Provider | Description |
|----------|----------|-------------|
| `RESEND_API_KEY` | Resend | API key from resend.com |
| `SENDGRID_API_KEY` | SendGrid | API key from sendgrid.com |
| `POSTMARK_SERVER_TOKEN` | Postmark | Server token from postmarkapp.com |
| `SMTP_HOST` | SMTP | Hostname of your SMTP server |
| `SMTP_PORT` | SMTP | Port — typically `587` (TLS) or `465` (SSL) |
| `SMTP_USER` | SMTP | SMTP login username |
| `SMTP_PASSWORD` | SMTP | SMTP login password |
| `SMTP_USE_TLS` | SMTP | `true` (default) or `false` |

### Other

| Variable | Description |
|----------|-------------|
| `CRM_OWNER_EMAIL` | Email of the owner account — used by `seed.py` to target the right user |

---

## Deployment

### Docker (recommended)

The app builds into a single container: FastAPI serves the pre-built React bundle as static files. No Vite or Node in production.

#### First-time setup

```bash
# 1. Clone the repo on your server
git clone https://github.com/thewoddlypenguin/crm-v2.git
cd crm-v2

# 2. Create .env
cp .env.example .env   # or create manually — see Environment Variables above
nano .env

# 3. Build and start
docker compose up -d --build

# 4. Check logs
docker compose logs app --tail=100
```

The app listens on `127.0.0.1:8000`. Put Nginx or Caddy in front to handle TLS and forward traffic.

#### Updating after a push

```bash
git pull
docker compose up -d --build --no-cache
```

The `--no-cache` flag ensures changed source files are always picked up. Without it, Docker may reuse a stale layer.

#### Database

The `db` service in `docker-compose.yml` runs Postgres 16 with a persistent named volume (`postgres_data`). Tables are created automatically on first boot via `Base.metadata.create_all()`. There is no migration tool — new columns on existing tables require a manual `ALTER TABLE` on the live database.

```bash
# Connect to the running DB container
docker compose exec db psql -U leverage -d leveragecrm
```

---

### Systemd (bare metal)

For direct server deployment without Docker.

#### Prerequisites

- Python 3.12+ and `uv` installed system-wide
- PostgreSQL running and accessible
- App deployed to `/var/www/leverage-crm`

#### Setup

```bash
# 1. Deploy files
sudo mkdir -p /var/www/leverage-crm
sudo cp -r . /var/www/leverage-crm/
cd /var/www/leverage-crm

# 2. Create .env
sudo nano .env   # see Environment Variables above

# 3. Create virtualenv and install deps
uv sync --no-dev

# 4. Build frontend
bun install --frozen-lockfile
bunx vite build
# Built output lands in ./dist — FastAPI serves it as static files

# 5. Install and start the service
sudo cp leverage-crm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable leverage-crm
sudo systemctl start leverage-crm

# 6. Check status
sudo systemctl status leverage-crm
sudo journalctl -u leverage-crm -n 100
```

#### Updating after a push

```bash
cd /var/www/leverage-crm
git pull
uv sync --no-dev
bun install --frozen-lockfile
bunx vite build
sudo systemctl restart leverage-crm
```

---

## Email Provider Setup

Email defaults to **test mode** — sends are simulated, logged to the activity feed as `[TEST MODE — not delivered]`, and never leave the server. This is safe to leave on indefinitely for a solo CRM.

### Activating a real provider

1. **Choose a provider** — Resend is the easiest to wire up.
2. **Set the credentials** as environment variables (in `.env` or your server's env config — never in the database).
3. **Implement the stub** in `email_service.py` — each provider has a `_send_via_<provider>()` function. Install the SDK with `uv add <package>` first.
4. **Disable test mode** in the app: Settings → Email → toggle off Test Mode → Save.

### Provider reference

#### Resend

```bash
# Install SDK
uv add resend

# .env
RESEND_API_KEY=re_...
```

```python
# email_service.py — implement _send_via_resend()
import resend
resend.api_key = os.environ["RESEND_API_KEY"]
response = resend.Emails.send({
    "from": f"{cfg.from_name} <{cfg.from_email}>",
    "to": payload.to_address,
    "subject": payload.subject,
    "text": payload.body,
})
return EmailResult(success=True, message_id=response["id"])
```

#### SendGrid

```bash
uv add sendgrid
# SENDGRID_API_KEY=SG....
```

#### Postmark

```bash
uv add postmarker
# POSTMARK_SERVER_TOKEN=...
```

#### SMTP

No extra SDK needed — uses Python's stdlib `smtplib`. Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.

---

## Troubleshooting

### App refuses to start — `RuntimeError: JWT_SECRET environment variable is not set`

`JWT_SECRET` is required. Generate one and add it to your `.env`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 502 / blank page after deploy

1. Check container logs: `docker compose logs app --tail=200`
2. Check the health endpoint: `curl http://localhost:8000/api/health`
3. Most common cause: a Python import error at startup (missing env var, bad dependency). The logs will show the traceback.

### UI looks wrong / changes not appearing after redeploy

Docker may have used a cached build layer. Force a clean rebuild:
```bash
docker compose down
docker compose build --no-cache app
docker compose up -d
```
Then hard-refresh the browser (Ctrl+Shift+R or open an incognito window).

### Settings → Email tab crashes the page (white screen)

shadcn `<Select>` components require non-empty string values. If you see this after a code change, check that no `<SelectItem value="">` exists — use a sentinel like `"none"` instead.

### Database: new column not appearing after model change

There is no Alembic. New *tables* are created automatically on boot. New *columns* on existing tables are not — run the ALTER manually:
```bash
docker compose exec db psql -U leverage -d leveragecrm -c \
  "ALTER TABLE leads ADD COLUMN my_new_col TEXT;"
```

### Registration is closed — `403 Registration is closed`

Expected — `REGISTRATION_ENABLED=false` is set. To create another account temporarily:
```bash
# In .env or docker-compose override:
REGISTRATION_ENABLED=true
# Restart, register, then set back to false.
```

### Rate limit hit — `429 Too Many Requests`

Limits are per-IP:
- Register: 5 requests/minute
- Login: 10 requests/minute  
- Email send: 20 requests/minute

Wait 60 seconds and try again. In development, restart the server to reset the in-memory counter.

### CORS errors in the browser console

Set `CORS_ORIGINS` to your exact frontend origin, including the scheme and port if non-standard:
```bash
CORS_ORIGINS=https://crm.example.com
# Multiple origins:
CORS_ORIGINS=https://crm.example.com,https://www.example.com
```
