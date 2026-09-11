# Lakewood IT Hotline — JSON API

REST API for the business-side and provider-side mobile apps. Returns JSON only (no HTML templates).

## Stack

| Layer | File | Role |
|-------|------|------|
| MySQL | `db.py` | Parameterized queries via PyMySQL |
| Redis | `redis.py` | Escalation flags, SMS pending offers, RQ queue |
| MinIO | `miniIO.py` | Photo storage + presigned URLs |
| Dispatch | `dispatch.py` | Twilio SMS to nearby providers on new tickets |
| Routes | `*_routes.py` | Flask blueprints per domain |
| App | `app.py` | Thin app factory + blueprint registration |

## Prerequisites

- Docker Desktop (MySQL, Redis, MinIO)
- Python 3.11+

## 1. Start infrastructure

```bash
cd /Users/k2/Desktop/IThotline
docker compose up -d
```

## 2. Load schema + seed data

```bash
mysql -h 127.0.0.1 -u ithotline -pithotline ithotline < IThotline.sql
```

If you already loaded an older schema, add the provider phone column:

```sql
ALTER TABLE ITWorker ADD COLUMN phone VARCHAR(20) NULL UNIQUE AFTER email;
```

Seed accounts use password **`password123`**, stored as a **bcrypt hash** in MySQL (not plain text).

If you loaded an older `IThotline.sql` that put literal `password123` in the `password` column, login will fail even when the email matches. Fix existing rows:

```bash
source .venv/bin/activate
python fix_seed_passwords.py
```

Then sign in with e.g. `lakewood.market@example.com` / `password123`.

**MySQL credentials:** copy `.env.example` to `.env` and set `DB_USER` / `DB_PASSWORD` to match your MySQL Workbench connection. The API defaults to `ithotline` / `ithotline` (docker-compose). If those do not match your server, every login returns a server error.

## 3. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 4. Start RQ worker (ticket escalation)

```bash
source .venv/bin/activate
rq worker ithotline --url redis://localhost:6379/0
```

When a ticket stays `open` for `TICKET_ESCALATION_MINUTES` (default 10), the worker flags it in Redis and re-notifies providers at **1.5× service radius** via SMS.

## 5. Start API

```bash
source .venv/bin/activate
python app.py
```

API listens on **http://localhost:5001** (see `PORT` in `.env`).

```bash
curl http://localhost:5001/health
```

## 6. Test with curl / REST Client

See **`api_examples.http`** for every endpoint, including a two-provider **claim race test**.

## Twilio (optional)

Set in `.env`:

- `TWILIO_ENABLED=true`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`

When disabled, SMS bodies are **logged** (dry-run) and ticket creation never fails.

Point Twilio inbound webhook to `POST /twilio/inbound`. Providers reply `YES` to claim the most recent offer stored in Redis for their phone.

## Mobile apps (businessSide / techSide)

Both Expo apps use **JWT auth** with tokens stored in **expo-secure-store**.

### Remote testers (any network — ngrok)

Remote users do **not** need to be on your Wi‑Fi. You need two tunnels: one for the Flask API and one for the Expo dev server (built into `--tunnel`).

**Terminal 1 — API**
```bash
source .venv/bin/activate
python app.py
```

**Terminal 2 — ngrok for Flask (port 5001)**
```bash
ngrok http 5001
```

**Terminal 3 — sync ngrok URL into all app `.env` files, then start Expo in tunnel mode**
```bash
python sync_ngrok.py
cd businessSide && npm run start:remote   # or techSide
```

Share the **Expo QR code / link** from the terminal. Testers open it in **Expo Go** from anywhere.

After each new ngrok session (URL changes), run `python sync_ngrok.py` again and restart Expo.

**Admin panel over ngrok:** run `cd admin-panel && npm run dev`, then `ngrok http 5173` in another terminal. Open the ngrok URL in a browser; API calls use `VITE_NGROK_API_URL` from `sync_ngrok.py`.

### Same Wi‑Fi only (local LAN)

`localhost` will not work from a phone. Set your machine's LAN IP:

```bash
cp businessSide/.env.example businessSide/.env
cp techSide/.env.example techSide/.env
# EXPO_PUBLIC_USE_NGROK=false
# EXPO_PUBLIC_API_URL=http://YOUR_LAN_IP:5001
```

Restart Expo after changing `.env`.

### Quick test logins

**Seed emails** (e.g. `lakewood.market@example.com`) use password **`password123`** after you run:

```bash
source .venv/bin/activate
python fix_seed_passwords.py   # one-time fix if you loaded old SQL with @pw placeholder
python make_test_user.py       # optional: adds test.business@ / test.provider@ accounts
```

New registrations get `status=pending` and see the pending-approval screen until an admin approves them in the DB.

### Run apps

```bash
cd businessSide && npm start          # same Wi‑Fi (LAN)
cd businessSide && npm run start:remote   # remote testers (ngrok + tunnel)
```

Same for `techSide`.

## Endpoints — business

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | No |
| POST | `/auth/business/register` | No |
| POST | `/auth/business/login` | No |
| GET | `/auth/me` | JWT (business or provider) |
| GET/PUT | `/business/me` | JWT (business) |
| GET | `/providers/available/count?lat=&lng=` | No |
| POST | `/tickets` | JWT (business) |
| GET | `/tickets/mine` | JWT (business) |
| GET | `/tickets/:id` | JWT (business or provider) |
| POST | `/tickets/:id/cancel` | JWT (business) |
| POST | `/tickets/:id/confirm` | JWT (business) |
| GET/POST | `/tickets/:id/messages` | JWT (business or assigned provider) |
| POST | `/photos` | JWT (business: problem photos) |

## Endpoints — provider

| Method | Path | Auth |
|--------|------|------|
| POST | `/auth/provider/register` | No |
| POST | `/auth/provider/login` | No |
| GET | `/auth/me` | JWT (business or provider) |
| GET/PUT | `/provider/me` | JWT (provider) |
| PUT | `/provider/availability` | JWT (provider) |
| GET | `/tickets/open?lat=&lng=` | JWT (approved + available) |
| POST | `/tickets/:id/claim` | JWT (provider) — atomic, 409 if lost race |
| POST | `/tickets/:id/status` | JWT (assigned provider) |
| POST | `/tickets/:id/complete` | JWT (assigned provider) |
| GET/POST | `/tickets/:id/messages` | JWT (assigned provider) |
| POST | `/photos` | JWT (provider: completion photos) |
| POST | `/twilio/inbound` | Twilio webhook |

## Security notes

- Parameterized SQL only; bcrypt passwords; JWT on protected routes.
- Businesses may only access their tickets; providers may only act on assigned tickets (except viewing/claiming open tickets).
- Claim uses conditional `UPDATE ... WHERE status='open' AND itid IS NULL` — concurrent claims yield exactly one winner.

## redis.py import note

The local file `redis.py` shadows the PyPI `redis` package. Import helpers as `import redis as redis_store`.
