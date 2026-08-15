# 🌍 Lead-Gen Bot — Africa Small-Business Website Pitcher 2

An autonomous, **100% free-tier, no credit card required** lead-generation system that:

1. Hunts small businesses across 🇿🇦 🇿🇼 🇿🇲 🇧🇼 🇰🇪 that have **no website**
2. Extracts every contact detail (email, phone, socials) it can find
3. Generates a **demo website** for each lead using free-tier AI (Cloudflare → Mistral → Cohere → Groq, with automatic fallback)
4. Hosts the demo on **GitHub Pages → Cloudflare Pages → Netlify** (auto-fallback)
5. Emails the lead via a **3-provider fallback chain**: Brevo (300/day) → Resend (100/day) → MailerSend
6. Sends timed follow-ups based on the lead's stage in your CRM
7. If a lead has **no email**, scrapes their socials and DMs them instead
8. Pings you on **Discord** with the lead's details when there's literally no contact info
9. Uses **Notion** as your CRM dashboard (free, no card, no Google Cloud)
10. Runs **twice daily** (09:00 + 15:00 CAT) on **Railway** (free, no card, 24/7)

> 🆕 **First time installing?** Read **[INSTALL.md](INSTALL.md)** — a complete cloud-only beginner's walkthrough. **No credit card required for any service.**
>
> 🆕 **Already installed?** Use **[CHEATSHEET.md](CHEATSHEET.md)** for the daily reference card.
>
> 🔄 **Updating the bot to a new version?** Read **[SYNC.md](SYNC.md)** for the 5-minute clean re-upload path.

> 💳 **$0/month, forever.** Notion + Railway + Brevo + Cloudflare + GitHub + Discord + Geoapify — all free-tier, all no-card.

---

## Table of Contents

1. [How the bot works (one diagram)](#how-the-bot-works)
2. [Quick start (15 min)](#quick-start)
3. [Free accounts you need to create](#free-accounts)
4. [Environment variables](#environment-variables)
5. [Google Sheet setup](#google-sheet-setup)
6. [Running locally](#running-locally)
7. [Running on GitHub Actions (free cron)](#running-on-github-actions)
8. [The 8-step flow in detail](#the-8-step-flow)
9. [Daily caps, warm-up, and safety](#safety)
10. [Templates](#templates)
11. [Troubleshooting](#troubleshooting)
12. [Cost summary (everything free)](#cost-summary)

---

## How the bot works

```
┌──────────────────────────────────────────────────────────────┐
│  1. WAKE  (cron at 09:00 & 15:00 CAT)                       │
│     └─► load lead_state.json (what's pending follow-ups)    │
├──────────────────────────────────────────────────────────────┤
│  2. HUNT  (free sources, no paid credits)                   │
│     ├─ Overpass API         — OSM businesses, no website tag│
│     ├─ Geoapify Places      — 3k credits/day                │
│     ├─ OpenCorporates       — official company registries   │
│     ├─ SerpAPI free tier    — 100 searches/month            │
│     ├─ Yelp Fusion          — 500 calls/day                 │
│     └─ Yellow Pages scrapers per country                    │
│                                                              │
│  Filters: 5 countries, all industries, NO website detected   │
│  Extract: name, address, phone, socials, hours, category     │
│  Dedupe: by sha1(phone+name+city)                            │
├──────────────────────────────────────────────────────────────┤
│  3. EMAIL CHECK                                             │
│     ├─ has email?  → step 4 (build demo + send)             │
│     └─ no email?   → step 6 (socials DM branch)             │
├──────────────────────────────────────────────────────────────┤
│  4. BUILD DEMO                                              │
│     ├─ AI: Cloudflare → Mistral → Cohere → Groq (fallback)  │
│     ├─ Template: 5-page static site (Home/About/Services/   │
│     │   Gallery/Contact) generated from scraped data         │
│     ├─ Host: GitHub Pages → Cloudflare Pages → Netlify      │
│     └─ Screenshot via headless Chromium                     │
├──────────────────────────────────────────────────────────────┤
│  5. SEND + TRACK                                            │
│     ├─ Email 1 (immediate): "Made you a site" + URL + shot  │
│     ├─ Lead state → "Contacted" in sheet                    │
│     └─ Schedule follow-ups:  +3d, +7d, +14d, +21d           │
├──────────────────────────────────────────────────────────────┤
│  6. NO-EMAIL BRANCH                                         │
│     ├─ Scrape IG/FB/LinkedIn/TikTok handles                 │
│     ├─ DM via Meta Graph API (free) or Instagrapi (free)     │
│     ├─ If no social either → Discord webhook + "no email"   │
│     └─ If DM fails → still log to "no email" tab            │
├──────────────────────────────────────────────────────────────┤
│  7. FOLLOW-UP LOOP  (runs every wake)                       │
│     ├─ Read sheet, find leads where status ∈ {Contacted,    │
│     │   No Response, Interested}                            │
│     ├─ Send appropriate template based on status + day count│
│     └─ When you flip to "Bought" → stop sequence            │
├──────────────────────────────────────────────────────────────┤
│  8. SLEEP  (next cron tick)                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick start

**Recommended: deploy to Railway in 10 minutes — your PC never runs anything.**

1. Read **[INSTALL.md](INSTALL.md)** — the complete cloud-only walkthrough
2. After install, the bot runs itself twice a day, forever

**Alternative: run locally for testing**

```bash
# Only do this if you want to test on your PC
cd leadbot
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# edit .env with your keys

python -m leadbot.sheets --init    # creates the 5 Google Sheet tabs
python bot.py --dry-run            # smoke test
python bot.py                      # real run
```

---

## Free accounts

You need **zero** paid accounts. Everything below is free-tier, no credit card.

| Service | What for | Free limit | Signup link |
|---|---|---|---|
| **Geoapify** | Places search | 3,000 credits/day | https://myprojects.geoapify.com |
| **Cloudflare Workers AI** | Site generation (default) | 10,000 neurons/day | https://dash.cloudflare.com → Workers → AI |
| **Mistral** | Site gen fallback | Generous free tier | https://console.mistral.ai |
| **Cohere** | Site gen fallback | 1,000 req/month | https://dashboard.cohere.com |
| **Groq** | Site gen fallback | Very generous | https://console.groq.com |
| **GitHub** | Pages hosting (default) | Unlimited public repos | https://github.com |
| **Cloudflare Pages** | Hosting fallback | Unlimited sites | https://dash.cloudflare.com → Pages |
| **Netlify** | Hosting fallback | 100 GB bandwidth/mo | https://app.netlify.com |
| **Resend** | Transactional email | 100/day, 3k/month | https://resend.com |
| **Discord** | Notifications | Unlimited webhooks | https://discord.com → Server settings → Integrations |
| **Google Cloud** | Sheets API | Generous free | https://console.cloud.google.com |
| **SerpAPI** *(optional)* | Google search snippets | 100/mo | https://serpapi.com |
| **Yelp Fusion** *(optional)* | Yelp businesses | 500/day | https://www.yelp.com/developers |
| **OpenCorporates** *(optional)* | Company registry | 200 req/month | https://opencorporates.com/api |

> **Note:** Even without SerpAPI, Yelp, and OpenCorporates, the Overpass + Geoapify combo alone produces thousands of leads per day per country. The optional services are bonuses.

---

## Environment variables

Copy `.env.example` → `.env` and fill these in:

```bash
# ─── AI providers (provide at least ONE) ──────────────────────
CLOUDFLARE_ACCOUNT_ID=         # from dash.cloudflare.com
CLOUDFLARE_API_TOKEN=          # Workers AI permission
MISTRAL_API_KEY=               # optional fallback
COHERE_API_KEY=                # optional fallback
GROQ_API_KEY=                  # optional fallback

# ─── Scrapers ─────────────────────────────────────────────────
GEOAPIFY_KEY=                  # REQUIRED for option 2
SERPAPI_KEY=                   # optional
YELP_API_KEY=                  # optional
OPENCORPORATES_KEY=            # optional

# ─── Hosting ──────────────────────────────────────────────────
GITHUB_TOKEN=                  # needs repo + pages permission
GITHUB_DEMO_ORG=your-username  # where demo sites live
CLOUDFLARE_PAGES_API_TOKEN=    # optional fallback
CLOUDFLARE_PAGES_ACCOUNT_ID=   # optional fallback
NETLIFY_TOKEN=                 # optional fallback

# ─── Email ────────────────────────────────────────────────────
RESEND_API_KEY=                # from resend.com
FROM_EMAIL=hello@yourdomain.com
FROM_NAME=Your Name

# ─── Discord ──────────────────────────────────────────────────
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# ─── Google Sheets ────────────────────────────────────────────
# Two options, pick one:
#   (a) service account JSON path
GOOGLE_SHEETS_CREDENTIALS=/abs/path/to/sheets-sa.json
#   (b) or base64-encoded JSON (for GitHub Actions)
# GOOGLE_SHEETS_CREDENTIALS_B64=...

GOOGLE_SHEET_ID=               # the long ID in the sheet URL

# ─── Socials (optional, for DM branch) ────────────────────────
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
FACEBOOK_PAGE_ACCESS_TOKEN=

# ─── Bot config ───────────────────────────────────────────────
COUNTRIES=ZA,ZW,ZM,BW,KE
DAILY_EMAIL_CAP=20             # hard cap across all countries
WARMUP_DAYS=14                 # ramp from 1 → cap over this many days
SEND_WINDOW_LOCAL_START=9      # hour of day, lead's local time
SEND_WINDOW_LOCAL_END=11       # hour of day, lead's local time
TIMEZONE_OFFSETS={"ZA":2,"ZW":2,"ZM":2,"BW":2,"KE":3}
LEAD_PAGE_SIZE=20              # leads per wake cycle
LOG_LEVEL=INFO
DRY_RUN=false
```

---

## Google Sheet setup

The bot uses 5 tabs. Create them automatically:

```bash
python -m leadbot.sheets --init
```

This creates:

- **Leads** — main CRM, one row per business
- **No Email** — leads without email that got a Discord ping
- **Templates** — every email & DM template
- **Logs** — timestamped event log (sends, errors, follow-ups)
- **Settings** — runtime overrides (pause all, country caps, etc.)

### Leads tab columns (don't reorder, don't rename)

```
A  name
B  country
C  city
D  category
E  address
F  phone
G  email
H  website
I  instagram
J  facebook
K  linkedin
L  tiktok
M  source                  (which scraper found it)
N  lead_score              (0–20 priority)
O  status                  (New / Contacted / No Response / Interested / Bought / Not Interested / Bounced / Paused)
P  demo_url
Q  screenshot_url
R  first_sent_at
S  last_touch_at
T  followup_count
U  notes
V  lead_id                 (sha1 hash, do not edit)
W  score_breakdown         (JSON string explaining the score)
```

### Statuses (set these by hand after reviewing the email)

| Status | What it means | What the bot does next |
|---|---|---|
| `New` | Fresh, not yet sent | Bot will email/demo on next wake |
| `Contacted` | First email sent | Schedules follow-up at +3d |
| `No Response` | You saw no reply after 7d | Sends follow-up #2 at +7d |
| `Interested` | They replied with interest | Sends follow-up #3 at +14d |
| `Bought` | They paid | Stops sequence |
| `Not Interested` | They said no | Stops sequence |
| `Bounced` | Hard bounce detected | Stops sequence, flags for review |
| `Paused` | You want to skip | Stops sequence |

---

## Running locally

```bash
# Dry run (no emails, no DMs, no deploys — just shows what would happen)
python bot.py --dry-run

# Full run
python bot.py

# Only the follow-up loop (no scraping)
python bot.py --followups-only

# Only the scrapers (no emails)
python bot.py --scrape-only

# Send only to a specific lead by name (for testing templates)
python bot.py --test-lead "Acme Plumbing Johannesburg"
```

---

## Running on GitHub Actions

1. Push this folder to a new GitHub repo
2. Go to **Settings → Secrets and variables → Actions**
3. Add every secret from `.env` (one per env var)
4. The included `.github/workflows/leadbot.yml` runs the bot **twice daily** at:
   - 09:00 CAT → 07:00 UTC
   - 15:00 CAT → 13:00 UTC

To trigger a manual run: **Actions → Lead Bot → Run workflow**.

Free tier limits: 2,000 min/month. Each run uses ~2 min, so 60 runs/month = 120 min. Plenty of headroom.

---

## The 8-step flow

See [How the bot works](#how-the-bot-works). The key files are:

| Step | File |
|---|---|
| Wake + loop | `bot.py` |
| Scrapers | `scrapers/*.py` |
| Enrichment + dedup | `enrich/*.py` |
| AI generation | `ai/site_generator.py` |
| Hosting deploy | `hosting/*.py` |
| Screenshot | `preview/screenshot.py` |
| Email send | `outreach/resend_client.py` |
| Follow-ups | `outreach/followup_scheduler.py` |
| Socials DM | `dm/*.py` |
| Discord ping | `notify/discord.py` |
| Sheets I/O | `sheets.py` |

---

## Safety

- **Per-country daily cap** (default 20) — set in `Settings` tab
- **Warm-up mode** — first 14 days, starts at 1/day and ramps to cap
- **Bounce auto-pause** — 3 bounces from the same domain → pause that domain
- **Unsubscribe link** in every email (Resend handles this)
- **Local-time send window** — 09:00–11:00 in the lead's country, never midnight
- **`Settings!pause_all = TRUE`** halts the whole bot instantly
- **Per-row `status = Paused`** skips individual leads
- **Idempotent** — re-running never duplicates or double-sends

---

## Templates

Edit copy in the `Templates` tab. Variables are `{{double_braces}}`:

```
Hi {{name}},

I made you a free demo website for {{business_name}} — takes 30 seconds to look at:
{{demo_url}}

[attached: screenshot of your new homepage]

If you like it, I can have the real version live on {{suggested_domain}} within 48 hours
for {{price}}. Reply YES and I'll send a quote.

— {{sender_name}}
```

---

## Troubleshooting

**"No data from Overpass"** — that mirror is busy. The bot tries 4 mirrors in sequence.

**"Resend 403"** — verify your `FROM_EMAIL` is on a domain you authenticated in Resend. Use their sandbox domain while testing.

**"Google Sheets 403"** — share the sheet with the service account email (looks like `something@project.iam.gserviceaccount.com`).

**"Playwright fails"** — run `playwright install --with-deps chromium` (the `--with-deps` flag is needed on Linux CI).

**"GitHub Pages 404 after deploy"** — Pages needs a `gh-pages` branch or `/docs` folder. The bot uses `gh-pages`. Make sure the repo is **public**.

**"Demo looks ugly"** — edit prompts in `ai/prompts.py` to refine. The prompt is the product.

---

## Cost summary

| Service | Cost |
|---|---|
| Overpass | **Free forever** |
| Geoapify | **Free** (3k credits/day) |
| Cloudflare Workers AI | **Free** (10k neurons/day) |
| Mistral / Cohere / Groq | **Free** (fallbacks) |
| GitHub Pages | **Free** (public repos) |
| Cloudflare Pages | **Free** (unlimited) |
| Netlify | **Free** (100GB/mo) |
| Resend | **Free** (100/day, 3k/month) |
| Discord | **Free** (webhooks) |
| Google Sheets API | **Free** |
| GitHub Actions | **Free** (2,000 min/mo) |
| **Total** | **$0** |

The only hard ceiling is Resend's 100 emails/day. When you outgrow that, the same `outreach/resend_client.py` interface accepts any SMTP/transactional provider.
