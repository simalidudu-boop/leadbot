# 🚀 Lead Bot — Cloud-Only Install Guide (NO credit card required)

> **Read every step. Don't skip ahead. Each step depends on the last.**
> Estimated time: **20-30 minutes**. After that, you can shut down your PC forever and the bot keeps running.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  YOUR LAPTOP (or phone, or any browser)                            │
│  • Read Gmail, view Notion CRM, check Discord                      │
│  • Edit code on GitHub.com (no install needed)                     │
│  • You can shut it down — bot doesn't care                        │
└────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ you read
                                │
┌────────────────────────────────────────────────────────────────────┐
│  GITHUB (private repo)                                             │
│  • Stores the bot's code                                           │
│  • Runs a daily backup health-check                                │
└────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ Railway pulls code on every deploy
                                │
┌────────────────────────────────────────────────────────────────────┐
│  RAILWAY (primary runner) — the bot's home                        │
│  • Runs 24/7 on a free Linux container (no card)                   │
│  • Cron: bot wakes at 09:00 + 15:00 CAT every day                 │
│  • Persistent disk for state + generated sites                     │
│  • Free tier: $5 credit (no card required)                         │
└────────────────────────────────────────────────────────────────────┘
                                │
                                │ bot calls
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│  FREE EXTERNAL SERVICES (none require a credit card)               │
│  • Notion API (CRM) — no card                                      │
│  • Cloudflare Workers AI (default site gen) — no card              │
│  • Mistral / Cohere / Groq (fallbacks) — no card                   │
│  • Brevo 300/day + Resend 100/day + MailerSend (email) — no card   │
│  • Discord (notifications) — no card                               │
│  • GitHub Pages / Cloudflare Pages / Netlify (hosting) — no card   │
│  • Overpass / Geoapify / Yelp / OpenCorporates (data) — no card    │
└────────────────────────────────────────────────────────────────────┘
```

**The whole stack is $0/month. Nothing requires a credit card. Nothing.**

---

## Table of contents

1. [GitHub (5 min)](#step-1-github-5-min)
2. [Free accounts — no card required (15 min)](#step-2-free-accounts-15-min)
3. [Notion CRM setup (8 min)](#step-3-notion-crm-5-min)
4. [Push code to GitHub (5 min)](#step-4-push-code-to-github-5-min)
5. [Deploy to Railway (10 min)](#step-5-deploy-to-railway-10-min)
6. [Verify it works (5 min)](#step-6-verify-5-min)
7. [GitHub backup health check (3 min)](#step-7-github-backup-3-min)
8. [Daily usage](#step-8-daily-usage)
9. [Editing code in the cloud](#step-9-editing-code-in-the-cloud)

---

## STEP 1: GitHub (5 min)

GitHub is where the bot's code lives. Free, no card, ever.

1. Go to **https://github.com/signup** and create an account
2. Verify your email
3. Once logged in, click **"+"** (top right) → **"New repository"**
4. Fill in:
   - **Repository name:** `leadbot`
   - **Description:** `Lead generation bot`
   - **Visibility:** `Private` ← important
   - **DO NOT** tick "Add a README file"
   - **DO NOT** add .gitignore or license
5. Click **"Create repository"**
6. Keep this tab open — you'll need it in Step 4

**Also create your GitHub access token** (used by the bot to deploy demo sites):

7. Click your profile picture (top right) → **Settings**
8. Scroll to the very bottom → click **"Developer settings"** (left sidebar)
9. **Personal access tokens** → **"Tokens (classic)"** → **"Generate new token"** → **"Generate new token (classic)"**
10. Fill in:
    - **Note:** `leadbot`
    - **Expiration:** `No expiration`
    - **Scopes:** ✅ `repo` (everything under it), ✅ `workflow`
11. Click **"Generate token"**
12. **Copy the token immediately** — you can't see it again. Save it somewhere safe (a password manager, a phone note, anywhere).
    - This is your **`GITHUB_TOKEN`**

---

## STEP 2: Free accounts — no card required (15 min)

Open a new browser tab for each. **Don't close the tabs** — you'll need them in Step 5.

### 2a. Cloudflare (REQUIRED for AI generation)

1. **https://dash.cloudflare.com/sign-up** → sign up (no card)
2. Left sidebar → **"Workers & Pages"** → if asked, pick **Free** plan
3. Right side → copy the **"Account ID"** (you'll need this)
   - This is your **`CLOUDFLARE_ACCOUNT_ID`**
4. Click **"Manage tokens"** (or go to https://dash.cloudflare.com/profile/api-tokens)
5. Click **"Create Token"** → **"Custom token"** at the bottom
6. Configure:
   - **Token name:** `leadbot`
   - **Permissions:**
     - Account → **Workers Scripts: Edit**
     - Account → **Account Settings: Read**
7. Click **"Continue to summary"** → **"Create Token"**
8. **Copy the token** (you'll never see it again)
   - This is your **`CLOUDFLARE_API_TOKEN`**

### 2b. Brevo (PRIMARY email provider — 300/day free, no card)

1. **https://www.brevo.com** → **Sign up free**
2. Verify email
3. Top right → click your name → **"SMTP & API"** → **"API Keys"** tab
4. Click **"Generate a new API key"** → name it `leadbot` → **"Generate"**
5. **Copy the key**
   - This is your **`BREVO_API_KEY`**

**Brevo's free tier restrictions:**
- 300 emails/day
- Your emails may have a small "via Brevo" footer
- You CAN send to anyone (unlike Resend's sandbox)

### 2c. Resend (fallback #1 — 100/day free, no card)

1. **https://resend.com/signup** → sign up
2. Verify email
3. Left sidebar → **"API Keys"** → **"Create API Key"**
4. Name: `leadbot`, permission: Full access → **"Add"**
5. **Copy the key**
   - This is your **`RESEND_API_KEY`**

**⚠️ Resend's catch:** until you verify a domain you own, you can only send to **yourself** (the email you signed up with). For real outreach, verify a domain (free, just needs DNS access). For testing, set `FROM_EMAIL=onboarding@resend.dev` and only test sends to your own email.

### 2d. MailerSend (fallback #2 — low-volume free, no card)

1. **https://www.mailersend.com** → **"Start for free"**
2. Verify email
3. Top right → **Settings** → **"API Tokens"** → **"Create API Token"**
4. Name: `leadbot`, scope: **"Email" full access** → **"Create token"**
5. **Copy the token**
   - This is your **`MAILERSEND_API_KEY`**

### 2b. Gmail via Apps Script (PRIMARY — 500/day free, no card)

This is the recommended email path. The bot calls a small Google Apps Script you deploy once, and the script uses your real Gmail to send.

1. Open **https://script.google.com** → **"New project"**
2. Replace everything in the editor with the contents of the file `outreach/gmail_apps_script_user_code.gs` from the GitHub repo (open it, select all, copy, paste)
3. Click **"Save"** (💾 icon, top right) — name the project `Lead Bot`
4. Click **"Deploy"** (top right) → **"New deployment"**
5. Click the gear ⚙️ icon → **"Web app"**
6. Fill in:
   - **Description:** `Lead Bot`
   - **Execute as:** Me (your account)
   - **Who has access:** Anyone
7. Click **"Deploy"**
8. Google asks you to authorize — click **"Authorize access"**, pick your Google account
9. You may see a scary "This app isn't verified" warning — click **"Advanced"** → **"Go to Lead Bot (unsafe)"** → **"Allow"**. (This is safe because only you have the deployment URL.)
10. Copy the **"Web app URL"** — it looks like:
    ```
    https://script.google.com/macros/s/AKfycbxxxxxxxxxxxxxxxxxxxx/exec
    ```
    - This is your **`GMAIL_WEBHOOK_URL`**

11. **Test it:** open a new browser tab, paste the URL. You should see a JSON response: `{"status":"ready",...}`. That means the webhook works.

12. **Send a test email** (optional): from a terminal (or a free online tool like https://reqbin.com), POST to the URL with this body:
    ```json
    {
      "to": "your-personal-email@gmail.com",
      "subject": "Lead Bot test",
      "body": "If you got this, the email pipeline works!"
    }
    ```
    You should get the email within seconds. The bot will do the same automatically.

### 2e. Geoapify (REQUIRED for second scraper)

1. **https://myprojects.geoapify.com** → sign up
2. Verify email
3. **"Create new project"** → name `leadbot` → **Create**
4. Click on the project → copy the **API Key**
   - This is your **`GEOAPIFY_KEY`**

### 2f. Discord (REQUIRED for no-email notifications)

1. **https://discord.com** → sign up (or use the app)
2. Create your own server: **"+"** (left sidebar) → **"Create My Own"** → **"For me and my friends"**
3. Right-click on a text channel (e.g. `#general`) → **"Edit Channel"**
4. Left sidebar → **"Integrations"** → **"Webhooks"** → **"New Webhook"**
5. Name it `leadbot`
6. Click **"Copy Webhook URL"**
   - This is your **`DISCORD_WEBHOOK_URL`**

### 2g. (Optional) Mistral, Cohere, Groq — AI fallbacks

If Cloudflare's daily neurons run out, the bot falls back to these. All free, all take ~2 min each to set up:

- **Mistral:** https://console.mistral.ai → API Keys
- **Cohere:** https://dashboard.cohere.com → API Keys
- **Groq:** https://console.groq.com → API Keys

---

## STEP 3: Notion CRM (8 min — no card, no Google Cloud)

This replaces Google Sheets as your CRM. Notion's free plan is genuinely free forever, no card required.

### 3a. Create a Notion account

1. Go to **https://www.notion.so/signup** → sign up with email
2. Verify your email

### 3b. Create an integration

1. Go to **https://www.notion.so/profile/integrations**
2. Click **"Develop your own integrations"** (or **"+ New integration"**)
3. Fill in:
   - **Name:** `leadbot`
   - **Logo:** (skip)
   - **Associated workspace:** select your workspace
   - **Type:** Internal
   - **Capabilities:** Read, Update, Insert content (tick all three)
4. Click **"Save"**
5. On the next screen, find **"Internal Integration Secret"** → click **"Show"** → **"Copy"**
   - This is your **`NOTION_API_KEY`** (starts with `secret_...`)

### 3c. Create a parent page

1. Open your Notion workspace
2. Click **"+ New page"** (in the sidebar)
3. Title: `Lead Bot` (or anything)
4. In the page, type anything (it doesn't matter — we just need the page to exist)

### 3d. Share the page with the integration

1. On the page you just made, click the **"•••"** (top right) → **"Connections"** → **"Connect to"**
2. Find and select your `leadbot` integration
3. Confirm

### 3e. Get the page ID

1. Look at your browser's URL bar. It looks like:
   `https://www.notion.so/My-Workspace/abc123def456...`
2. The 32-character hex string is the page ID. Copy it (you can include or exclude the dashes — the bot handles both).
   - This is your **`NOTION_PARENT_PAGE_ID`**

That's it. The bot will create the 5 databases (Leads, No Email, Templates, Logs, Settings) inside this page on first run.

---

## STEP 4: Push code to GitHub (5 min, browser only)

1. **Download the code:** ask me (the assistant) for the `leadbot.zip` file. I'll provide a download link.
2. **Unzip it.** On Windows: right-click → "Extract All…". On Mac: double-click. On Linux: `unzip leadbot.zip`.
3. Open the unzipped `leadbot/` folder. You'll see files like `bot.py`, `INSTALL.md`, `requirements.txt`, and folders like `ai/`, `outreach/`, `notion_crm.py`, etc.
4. In your browser, go to your empty `leadbot` repo on GitHub
5. Click **"Add file"** → **"Upload files"**
6. **Drag and drop** all the contents of the unzipped `leadbot/` folder into the upload area. **Important:** drop the *contents* (the individual files and subfolders), not the `leadbot/` folder itself.
7. Wait for the upload to show all 50+ files
8. Type commit message: `initial commit`
9. Click **"Commit changes"**
10. Wait for the upload to finish. You'll see all the files in the repo.

To edit code later, click any file in GitHub → pencil icon → edit → commit. **No PC ever needed.**

### 4b. (Optional) Get a Netlify token for fallback demo hosting

The bot already works with GitHub Pages + Cloudflare Pages. If you want Netlify as an extra fallback (in case GitHub and Cloudflare both rate-limit you), set up a token:

1. Go to **https://app.netlify.com** and sign up (free, no card)
2. Once logged in, click your profile picture (top right) → **User settings**
3. Left sidebar → **"Applications"** → **"Personal access tokens"**
4. Click **"New access token"**
5. Description: `leadbot`
6. Click **"Generate token"**
7. **Copy the token** (you'll never see it again)
   - This is your **`NETLIFY_TOKEN`**

8. In Railway, add `NETLIFY_TOKEN=<paste-the-token>` to your env vars (we'll do that in Step 5c)

---

## STEP 5: Deploy to Railway (10 min, no card)

Railway is where the bot runs 24/7. Free tier: $5 credit, no card required.

### 5a. Create Railway account

1. Go to **https://railway.app**
2. Click **"Start a New Project"** → **"Login with GitHub"**
3. Authorize Railway to access your GitHub repos

### 5b. Create a project from your GitHub repo

1. Click **"New Project"** → **"Deploy from GitHub Repo"**
2. Find and click `leadbot`
3. Railway starts building automatically. **It will fail** — that's normal, you haven't added env vars yet.

### 5c. Add environment variables

1. In Railway, click on the `leadbot` service (the box)
2. Click the **"Variables"** tab
3. Click **"+" New Variable"** for each one below. Type the Variable Name on the left, the Value on the right.

**Required variables** (copy from your accounts in Step 2 and 3):

| Variable Name | Value |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | from Step 2a |
| `CLOUDFLARE_API_TOKEN` | from Step 2a |
| `GEOAPIFY_KEY` | from Step 2e |
| `GMAIL_WEBHOOK_URL` | from Step 2b (Apps Script deployment URL) |
| `MAILERSEND_API_KEY` | from Step 2d (fallback) |
| `BREVO_API_KEY` | (optional) from Step 2b — only if you set up Brevo |
| `RESEND_API_KEY` | (optional) from Step 2c — only if you set up Resend |
| `FROM_EMAIL` | your Gmail address (e.g. `you@gmail.com`) — used by MailerSend/Brevo/Resend |
| `FROM_NAME` | your name, e.g. `Tendai from XYZ Web` |
| `DISCORD_WEBHOOK_URL` | from Step 2f |
| `GITHUB_TOKEN` | from Step 1 |
| `GITHUB_DEMO_ORG` | your GitHub username |
| `NOTION_API_KEY` | from Step 3b (starts with `secret_`) |
| `NOTION_PARENT_PAGE_ID` | from Step 3e (32-char hex string) |
| `DRY_RUN` | `false` |
| `LOG_LEVEL` | `INFO` |
| `DAILY_EMAIL_CAP` | `20` |
| `WARMUP_DAYS` | `14` |
| `SEND_WINDOW_LOCAL_START` | `9` |
| `SEND_WINDOW_LOCAL_END` | `11` |
| `LEAD_PAGE_SIZE` | `20` |
| `COUNTRIES` | `ZA,ZW,ZM,BW,KE` |
| `TIMEZONE_OFFSETS` | `{"ZA":2,"ZW":2,"ZM":2,"BW":2,"KE":3}` |

**Optional (only if you set them up):**
- `MISTRAL_API_KEY`, `COHERE_API_KEY`, `GROQ_API_KEY` (AI fallbacks)
- `SERPAPI_KEY`, `YELP_API_KEY`, `OPENCORPORATES_KEY` (extra scrapers)
- `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD` (Instagram DM)

**Notes on `FROM_EMAIL`:**
- Brevo lets you send from any email until you verify a domain. Set this to **any email you have access to** and add it as a sender in Brevo: **https://app.brevo.com/settings/keys/senders**
- If Brevo rejects your email, the bot falls back to Resend. If Resend's also unverified, it falls back to MailerSend.

### 5d. Add a persistent volume (so the bot remembers state)

1. In your Railway service, click **"Settings"** tab
2. Scroll to **"Volumes"** → **"Add Volume"**
3. Add:
   - Mount path: `/app/state`, size: 1 GB
   - Mount path: `/app/data`, size: 5 GB
4. Click **"Add"** for each

> Without volumes, the bot loses its daily counters and re-sends the same emails every restart. Don't skip this.

### 5e. Wait for the deploy

1. Click the **"Deployments"** tab
2. Click the most recent deployment to watch logs
3. After 1-3 minutes, look for:
   - ✅ **"Build successful"** + **"Deployment live"** → great
   - ❌ **"Deployment failed"** → click the failed step, read the error, fix it (usually a missing/typo'd env var), and the deploy auto-retries

---

## STEP 6: Verify (5 min)

1. In Railway, **Deployments** → click the latest successful one → **"View Logs"**
2. You should see:
   ```
   === Lead Bot starting — 2026-08-15T07:00:00 ===
   STEP 7: Follow-up loop
   STEP 2: HUNT — scraping free data sources
   Overpass: ZA bbox=...
   Overpass: ZA → 47 elements
   ...
   ```
3. **If "All AI providers failed":** Cloudflare token is wrong — check the env var
4. **If "Notion 401":** `NOTION_API_KEY` is wrong or the integration doesn't have access to the parent page
5. **If "Brevo 401":** your `BREVO_API_KEY` is wrong
6. **If "Brevo 403 sender not verified":** add the `FROM_EMAIL` as a sender in Brevo (https://app.brevo.com/settings/keys/senders)

Wait 5-10 minutes for the run to finish. Then:

7. **Open Notion** in your browser → open the `Lead Bot` page you created → you should see 5 new databases at the bottom: **Lead Bot — Leads**, **Lead Bot — No Email**, **Lead Bot — Templates**, **Lead Bot — Logs**, **Lead Bot — Settings**
8. Click **"Lead Bot — Leads"** — you should see new rows appearing with business names, contact info, and statuses
9. **Open Discord** — you should see alerts for leads with no email
10. **Check the email inbox** you set as `FROM_EMAIL` — you should see a real demo email from the bot

🎉 **If all 3 of those worked, the bot is fully operational.**

---

## STEP 7: GitHub backup health check (3 min)

1. In your GitHub repo, go to **Settings** → **Secrets and variables** → **Actions**
2. **"New repository secret"**:
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: paste your Discord webhook URL
3. **Add secret**
4. The workflow file is already in the repo (`.github/workflows/leadbot.yml`). It pings Discord daily at 06:00 UTC.

You can trigger it manually: **Actions** tab → **Lead Bot** → **Run workflow**.

---

## STEP 8: Daily usage

### Schedule (your bot's day)

The bot runs **three sub-runs** in the morning, spaced 40 minutes apart, to spread the load:

| Slot | UTC | Local (SAST / CAT) | What happens |
|---|---|---|---|
| Sub-run 1 | 07:00 | 09:00 | Process 1/3 of today's leads |
| Sub-run 2 | 07:40 | 09:40 | Process 1/3 of today's leads |
| Sub-run 3 | 08:20 | 10:20 | Process 1/3 of today's leads |

Leads are round-robined by score (highest scored across the three, then second-highest, etc.) so each slot gets a balanced mix.

**There is no 15:00 run anymore.** Anything that doesn't fit in the morning window gets picked up the next morning.

Your daily routine is:

### ☀️ Morning (5 min)

1. Open **Gmail** on your phone or any browser
2. Search for emails from your `FROM_EMAIL`
3. For each new reply:
   - They want to know more? → in Notion, change Status to `Interested`
   - They said "stop"? → change Status to `Not Interested`
   - They asked for a quote? → reply directly with your pricing, change Status to `Interested`
4. For leads where you got no reply in 7 days → change Status to `No Response`

### 🌙 Anytime (1 min)

5. **Check Discord** for 🚨 alerts about leads with no email — find their email yourself, add it to the Notion row, change Status to `New`, bot picks it up next run

### 📊 Weekly (10 min)

6. Open Notion → **Lead Bot — Leads** → check the stats
7. Open **Lead Bot — Logs** → look for any errors

### 🛑 Emergency stop

In Notion → **Lead Bot — Settings** → find the row with Key `pause_all` → change Value to `TRUE`. Bot stops. Set back to `FALSE` to resume.

---

## STEP 9: Editing code in the cloud (no PC needed)

To tweak the AI prompt, change email copy, etc.:

1. Go to your GitHub repo in a browser
2. Navigate to the file (e.g. `ai/prompts.py`)
3. Click the **pencil icon** (✏️) at the top right
4. Make your changes
5. Click **"Commit changes"**
6. Railway auto-detects the change and redeploys within 1-2 minutes

For bigger changes, use **GitHub Codespaces** (free 60 hours/month) — a full VS Code in the browser:

1. In your repo, click the green **"Code"** button → **"Codespaces"** tab → **"Create codespace"**
2. A full VS Code opens in your browser
3. Edit, save, commit → Railway deploys automatically

---

## 🎉 You're done!

The bot now:
- Runs at 9 AM and 3 PM every day, automatically
- Scrapes thousands of small businesses in 5 African countries that don't have websites
- Generates a free demo site for each
- Emails the lead via Brevo (or Resend/MailerSend as fallback)
- Logs everything to your Notion CRM
- Sends you Discord pings for leads that need manual help
- Sends follow-ups automatically based on the lead's status

**Your only daily job:** check Gmail twice a day, look at replies, update statuses in Notion.

---

## Quick troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Railway deploy fails immediately | Missing env var | Compare to list in Step 5c |
| "All AI providers failed" | Cloudflare token wrong | Regenerate token with right permissions |
| "Notion 401" | Wrong API key or no page access | Re-do Step 3b and 3d |
| "Brevo 401" | Wrong API key | Re-generate in Brevo |
| "Brevo 403 sender" | Your `FROM_EMAIL` not in Brevo | Add it at https://app.brevo.com/settings/keys/senders |
| "Resend 403" | `FROM_EMAIL` not verified | Use `onboarding@resend.dev` for testing |
| Bot runs but finds 0 leads | OSM coverage thin in your bbox | Try a different country or city |
| Lead has wrong info | OSM data is dirty | Use it as a starting point, verify on Google before pitching |
| Demo site looks ugly | AI prompt needs tuning | Edit `ai/prompts.py` on GitHub |
| Emails going to spam | Sender not verified | Verify your domain in Brevo (free, 10 min) |
| "All email providers failed" | None of the providers are configured | Set `GMAIL_WEBHOOK_URL` (Step 2b) or `MAILERSEND_API_KEY` (Step 2d) |

---

## Cost summary

| Service | Cost | Card required? |
|---|---|---|
| GitHub (private repo) | $0 | No |
| Railway (24/7 worker) | $0 for first $5/mo of usage | No |
| Notion (CRM) | $0 | No |
| Cloudflare Workers AI | $0 (10k neurons/day) | No |
| Mistral / Cohere / Groq | $0 (fallbacks) | No |
| Brevo | $0 (300/day) | No |
| Resend | $0 (100/day) | No |
| MailerSend | $0 (low-volume) | No |
| Geoapify | $0 (3k credits/day) | No |
| Discord | $0 | No |
| GitHub Pages / Cloudflare Pages / Netlify | $0 | No |
| **Total** | **$0** | **NEVER** |

If you outgrow the free tiers:
- Railway: $5/mo for 500 hours
- Brevo: $9/mo for 20k emails
- Notion: $10/mo for unlimited

Total monthly cost at scale: **~$25/mo** for ~5,000 emails/day.

---

## What now?

Shut down your laptop, take the rest of the day off. The bot is hunting, generating, emailing, and following up — all without you. 🤖
