# DocuSage — finish deploy

Follow the steps in order. Each step has a check; do not move on until the check passes.

**Your facts**

| Item | Value |
| --- | --- |
| Azure VM | `docusage-api` · Central India · B2as_v2 (2 vCPU / 8 GB) |
| Public IP | `135.235.219.214` |
| SSH | `ssh azureuser@135.235.219.214` |
| Repo | `https://github.com/AtifSaeed-10/ai-knowledge-assistant` · branch `v2-development` |
| Code on VM | `~/docusage` |
| Supabase project URL | `https://ondqhivitknekobigtdi.supabase.co` |
| Azure credit | $100 until 05/09/2027 · VM ~$0.05/hr (~$36/month) |

Never paste passwords, the JWT secret, `ghp_` tokens, or `.env` contents into a chat.

**Already working**

- Azure API is live: `http://135.235.219.214:8000/health` returns `{"status":"ok"}`
- Guest upload and indexing work on the VM (verified end to end)
- SQLite + Chroma live on the VM disk and survive rebuilds

**Still to do**

- Google sign-in: Supabase now issues **ES256** tokens. The fix is on the laptop but not yet on the VM, so signing in currently bounces back to guest.
- Vercel frontend, production auth URLs, and HTTPS for the API.

---

## Step 0 — Laptop: make `requirements.txt` UTF-8

The file is UTF-16, which makes `pip` fail inside Docker. In PowerShell at `c:\document_assistant`:

```powershell
$t = [IO.File]::ReadAllText("requirements.txt", [Text.Encoding]::Unicode)
[IO.File]::WriteAllText("requirements.txt", ($t -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding($false)))
Get-Content requirements.txt
```

**Check:** clean lines print, including `rank_bm25` and `cryptography`. No `f\x00a\x00s\x00t` garbage.

---

## Step 1 — Laptop: push the sign-in fix

```powershell
git add app_platform backend.py requirements.txt frontend/src test_platform_quotas.py test_platform_api.py test_support.py
git commit -m "Accept Supabase ES256 tokens and pin missing runtime deps"
git push origin v2-development
```

Never `git add .env` or `frontend/.env.local`.

**Check:** `git status --short` shows none of the files above as modified.

---

## Step 2 — VM: pull and rebuild

```bash
ssh azureuser@135.235.219.214
cd ~/docusage
git pull
sudo docker compose up -d --build
curl http://localhost:8000/health
```

Rebuild takes 3–10 minutes.

**Check:** `{"status":"ok"}`.

If it crashes, read the reason:

```bash
sudo docker compose logs --tail=60
```

---

## Step 3 — VM: CORS and auth provider

```bash
nano ~/docusage/.env
```

Set these two lines (no spaces around commas):

```env
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
AUTH_PROVIDER=supabase
```

`SUPABASE_URL` must already be present — ES256 verification reads the public keys from it. Save with `Ctrl+O`, Enter, `Ctrl+X`, then:

```bash
sudo docker compose up -d
```

**Check:** `curl http://localhost:8000/health` still returns ok.

---

## Step 4 — Laptop: test against the Azure API

`frontend/.env.local` must contain:

```env
NEXT_PUBLIC_API_URL=http://135.235.219.214:8000
```

```powershell
cd c:\document_assistant\frontend
npm run dev
```

Open **`http://localhost:3000`**. If the terminal says `Port 3000 is in use, trying 3001`, stop it, close the other Next.js window, and start again — a page served from `3001` is blocked unless that origin is in `CORS_ORIGINS`.

**Check, in this order:**

1. Workspace loads with no red banner
2. Small text PDF uploads and reaches **Ready**
3. One question returns an answer with a citation and a highlight
4. Sign in with Google — the avatar stays; it must not bounce back to guest
5. Profile menu shows name and email; Sign out returns you to a guest workspace

If step 4 says "Your session has expired", the VM did not pick up the ES256 fix. Go back to Step 2 and confirm `git pull` actually pulled.

---

## Step 5 — Vercel: deploy the frontend

1. [https://vercel.com](https://vercel.com) → sign in with **GitHub**
2. **Add New… → Project** → `ai-knowledge-assistant`
3. **Root Directory:** `frontend`
4. Framework: Next.js (auto-detected)
5. Environment variables:

| Name | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://135.235.219.214:8000` |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://ondqhivitknekobigtdi.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the same **anon public** key as `frontend/.env.local` |

6. Deploy and note the URL, e.g. `https://docusage.vercel.app`

**Check:** the page loads. Chat may fail until Step 7 — that is the expected mixed-content block, not a bug.

---

## Step 6 — Production auth URLs

Supabase → **Authentication → URL Configuration**

- Site URL: your Vercel URL
- Redirect URLs: both `http://localhost:3000` and your Vercel URL

Google Cloud → **APIs & Services → Credentials** → your OAuth **Web client**

- Authorized JavaScript origins: `http://localhost:3000` and your Vercel URL
- Authorized redirect URIs: keep `https://ondqhivitknekobigtdi.supabase.co/auth/v1/callback`

VM `.env` — add the Vercel URL:

```env
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,https://YOUR-APP.vercel.app
```

```bash
sudo docker compose up -d
```

**Check:** Google sign-in works from the Vercel URL.

---

## Step 6b — Professional Google sign-in (hide `….supabase.co`)

Google shows **“to continue to ondqhivitknekobigtdi.supabase.co”** because the OAuth redirect host is your Supabase project URL. The DocuSage UI cannot change that line. Do this in order.

### 1. Name the app in Google (required)

1. Open [Google Cloud Console](https://console.cloud.google.com/) → the project that owns the OAuth client  
2. **APIs & Services → OAuth consent screen**  
3. Set:
   - **App name:** `DocuSage`
   - **User support email:** `saeedatif199@gmail.com`
   - **App logo:** a square PNG (optional but looks finished)
   - **Application home page:** `https://www.docusage.tech` (or your live Vercel URL)
   - **Authorized domains:** `docusage.tech` and `supabase.co`
4. **Save**
5. **Audience:** keep **Testing** for now. Under **Test users**, add `saeedatif199@gmail.com` (and any demo Gmail). Only those accounts can sign in until the app is published.

### 2. Point Supabase at your real site (required)

Supabase → **Authentication → URL Configuration**

- **Site URL:** `https://www.docusage.tech` (production) — for local demos also keep `http://localhost:3000` in **Redirect URLs**
- **Redirect URLs** (one per line):
  - `http://localhost:3000`
  - `http://localhost:3000/**`
  - `https://www.docusage.tech`
  - `https://www.docusage.tech/**`
  - your Vercel URL if different

Wait 1–2 minutes after saving.

### 3. Custom auth domain (this removes `….supabase.co` from Google)

Google always prints the **callback hostname**. To show `auth.docusage.tech` instead of `ondqhivitknekobigtdi.supabase.co`:

1. You need a domain you control (`docusage.tech`)
2. Supabase → **Project Settings → Custom Domains** (Auth custom domain; Pro plan)  
   or follow [Custom domains for Auth](https://supabase.com/docs/guides/platform/custom-domains)
3. Add a DNS CNAME, e.g. `auth.docusage.tech` → the host Supabase gives you
4. When it is **Active**, Google Cloud → **Credentials → Web client**:
   - **Authorized JavaScript origins:** `https://www.docusage.tech`, `http://localhost:3000`
   - **Authorized redirect URIs:**  
     `https://auth.docusage.tech/auth/v1/callback`  
     (keep the old `https://ondqhivitknekobigtdi.supabase.co/auth/v1/callback` until the new one works, then remove it)
5. Supabase → **Authentication → URL Configuration** → set Site URL to `https://www.docusage.tech`

After DNS + Google both update, the consent screen reads like **Sign in to DocuSage** / **to continue to auth.docusage.tech**.

### 4. Unlimited questions for the operator account

On the **API** `.env` (laptop and Azure VM):

```env
ADMIN_EMAILS=saeedatif199@gmail.com
```

Restart the API (`uvicorn` locally, or `sudo docker compose up -d` on the VM). Sign in with that Google account. Only this email is unlimited; every other signed-in user stays on the normal monthly cap.

**Check:** after sign-in, `/me/usage` has `"admin": true` and `"unlimited": true`. Asking many questions does not open the signup/limit modal.

---

## Step 7 — HTTPS for the API

An HTTPS page cannot call `http://135.235.219.214:8000`; the browser blocks it. Put a free Cloudflare Tunnel in front of the API. On the VM:

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
./cloudflared tunnel --url http://localhost:8000
```

It prints a `https://something.trycloudflare.com` URL. Then:

1. Vercel → Settings → Environment Variables → `NEXT_PUBLIC_API_URL` = that HTTPS URL → **Redeploy**
2. VM `.env` → add the same HTTPS URL to `CORS_ORIGINS` → `sudo docker compose up -d`

The quick tunnel dies when you close the SSH session. To keep it up:

```bash
nohup ./cloudflared tunnel --url http://localhost:8000 > ~/tunnel.log 2>&1 &
grep trycloudflare ~/tunnel.log
```

A quick tunnel gets a **new URL every restart**. For a stable address, create a named tunnel with a Cloudflare account and a domain.

**Check:** upload and chat work from the Vercel URL.

---

## Step 8 — Acceptance tests

1. Guest: 1 PDF, one question, citation and highlight visible
2. Google sign-in survives a page refresh
3. Sign out returns a clean guest workspace
4. A second Google account cannot see the first account's PDFs
5. After the guest question limit, the signup modal appears
6. Deleting a PDF frees the upload slot

---

## Step 9 — Housekeeping

- GitHub → Settings → Developer settings → Personal access tokens → delete the `vm-clone` token
- Azure → VM → Public IP → set assignment to **Static**, or the IP can change and break Vercel
- Azure auto-shutdown stays **off** while you are demoing
- Not demoing? Portal → VM → **Stop** to save credit. Disk and data stay.

---

## What each piece does

| Piece | Where | Job |
| --- | --- | --- |
| Next.js | Vercel | UI, PDF viewer, sign-in |
| FastAPI | Azure Docker | upload, chat, citations, quotas |
| SQLite + `data/` | Azure disk | users, guests, documents, chats, PDF files |
| Chroma | Azure disk | embeddings |
| Supabase | cloud | Google login only |
| Groq (in `.env`) | API keys | LLM answers |
| RAG files (`rag.py`, etc.) | unchanged | retrieval; not touched for hosting |

There is no separate hosted database. `init_db()` in `database/db.py` creates the tables and applies `database/migrations/001_platform.sql` on every API start.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ssh` timeout | VM stopped, or NSG port 22 closed |
| Health works on VM only | NSG rule for TCP 8000 |
| pip `Invalid requirement: 'f\x00a\x00s\x00t...'` | UTF-16 `requirements.txt` — Step 0 |
| `ModuleNotFoundError: rank_bm25` | dependency missing from `requirements.txt`; add it and rebuild |
| "Your session has expired" after Google sign-in | VM still runs the HS256-only build — Step 2 |
| "Can't reach the DocuSage server" | frontend is on `3001`, or that origin is not in `CORS_ORIGINS` — Step 4 |
| Workspace loads but chat is silent from Vercel | mixed content HTTPS → HTTP — Step 7 |
| Google redirect error | Step 6 URLs, then wait 1–2 minutes |
| Upload says "Processing failed" | the PDF is scanned or has no text layer; try a text PDF |
| "The free trial covers 1 document" | guest limit; delete the existing PDF or sign in |
| Out of memory in logs | B2as_v2 has 8 GB; do not downgrade to B1s |
| PDFs gone after rebuild | confirm `./data` and `./chroma_db` are still mounted in `docker-compose.yml` |