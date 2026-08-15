# 📋 Lead Bot — Quick Reference Card

Print this. Tape it to your wall.

> **Your PC is not involved.** The bot runs on Railway. You only need a browser.

---

## Daily routine (5 min)

1. **Open Gmail** → search for emails from your `FROM_EMAIL`
2. **Open Notion** → your `Lead Bot` page → `Lead Bot — Leads` database
3. For each new lead with a reply: change Status accordingly
4. For leads with no reply after 7 days: change Status to `No Response`
5. **Check Discord** for 🚨 alerts about leads with no email

That's it. Bot does the rest.

---

## URLs you'll bookmark

| Link | What |
|---|---|
| **https://railway.app** | Your bot's home (check logs, env vars, restart) |
| **https://github.com/YourUsername/leadbot** | Your code (edit prompts, templates) |
| **https://www.notion.so** | Your CRM (read/update leads) |
| **Your Discord server** | Alerts |
| **Gmail** | See replies |

---

## Common actions

| What you want | How |
|---|---|
| Edit the email template | github.com → `outreach/templates` are stored in Notion's `Lead Bot — Templates` db → edit there |
| Edit the AI prompt | github.com → `ai/prompts.py` → pencil icon → edit → commit |
| Pause the bot | Notion → `Lead Bot — Settings` → find `pause_all` → set to `TRUE` |
| Restart the bot | Railway → `leadbot` service → **"Restart"** |
| Check today's logs | Railway → Deployments → click the latest → "View Logs" |
| Add a new env var | Railway → Variables → "+ New Variable" |

---

## What each file does (in 10 seconds)

| File | Purpose |
|---|---|
| `bot.py` | The main entry point. Don't edit. |
| `run.py` | Railway entry point. Long-lived scheduler. Don't edit. |
| `config.py` | Country list, scoring rules, defaults. Safe to edit. |
| `ai/prompts.py` | The exact prompt sent to the AI. **Edit this to change how sites look.** |
| `notion_crm.py` | The Notion CRM wrapper. Don't edit. |
| `outreach/email_providers.py` | The Brevo → Resend → MailerSend chain. Don't edit. |
| `.env` | Your secret keys (Railway side). **Never commit.** |
| `INSTALL.md` | Full setup guide. |
| `README.md` | Full reference. |

---

## What each Notion database does

| Database | What you do with it |
|---|---|
| **Lead Bot — Leads** | Your main CRM. Read statuses, set follow-ups. |
| **Lead Bot — No Email** | Leads that need a human to find contact info. Check Discord for these. |
| **Lead Bot — Templates** | Edit email/DM copy here. Changes apply next run. |
| **Lead Bot — Logs** | Read when something goes wrong. Timestamped. |
| **Lead Bot — Settings** | `pause_all=TRUE` stops the whole bot instantly. |

---

## Lead status workflow

```
  ┌──────┐
  │  New │ ← bot filled it in
  └──┬───┘
     │  bot sends first email
     ▼
  ┌───────────┐
  │ Contacted │ ← you saw the email go out
  └──┬────────┘
     │  you read the lead's reply (or didn't)
     │
     ├── 3 days later, no reply?   → set to "No Response"   (bot sends follow-up)
     ├── they replied positively?  → set to "Interested"    (bot sends warmer)
     ├── they said no?            → set to "Not Interested" (bot stops)
     ├── they paid?               → set to "Bought"         (bot stops)
     └── they replied STOP?       → set to "Bounced"        (bot stops + blocks domain)
```

**The bot will NOT auto-advance statuses.** You must look at Gmail and set them yourself.

---

## Daily limits

| Service | Free limit | What happens if you hit it |
|---|---|---|
| Brevo email | 300/day | Bot falls back to Resend |
| Resend email | 100/day | Bot falls back to MailerSend |
| MailerSend | low-volume | Bot stops sending, no error |
| Cloudflare AI | 10,000 "neurons"/day | Bot falls back to Mistral → Cohere → Groq |
| Geoapify | 3,000 credits/day | Bot scraper skips that call, no error |
| Notion API | 3 req/sec | Bot auto-throttles |
| Railway | $5 credit (~30 days) | Bot pauses, asks you to upgrade to $5/mo Hobby plan |

---

## Emergency stop

In Notion → **Lead Bot — Settings** database → find the row with Key `pause_all` → change Value to `TRUE`.

Bot won't run again until you set it back to `FALSE`.

---

## When something breaks

1. Check **Railway logs** — Deployments tab → click latest → "View Logs"
2. Check **Notion → Lead Bot — Logs** — last events
3. Check **Discord** — bot pings you for hard errors
4. Check **Gmail** for bounces

If still stuck: github.com → edit the relevant file → commit → Railway auto-redeploys.
