# 🔄 How to sync the latest bot code to GitHub (5 min, no Python needed)

You need this whenever the bot's code changes (new features, bug fixes).
This guide assumes you don't have Python installed and you want a
zero-install, browser-only workflow.

---

## Option A: Clean re-upload (5 min, recommended)

**Best for:** when many files changed (like now).

### Step 1: Download the latest zip

Get the latest `leadbot.zip` from the assistant.

### Step 2: Unzip it

- Windows: right-click → "Extract All…"
- Mac: double-click
- Linux: `unzip leadbot.zip`

You should see a folder called `leadbot/` with all the files inside.

### Step 3: Delete your current GitHub repo

⚠️ **This deletes everything. Your Railway env vars and Notion data are safe — those live elsewhere.**

1. Go to **https://github.com/simalidudu-boop/leadbot** (use your actual repo URL)
2. Click **"Settings"** (top tab)
3. Scroll all the way down to the **"Danger Zone"** (red box at the bottom)
4. Click **"Delete this repository"**
5. Type the repo name to confirm (it'll ask you to type `simalidudu-boop/leadbot`)
6. Click **"Delete"**
7. Confirm by entering your password

### Step 4: Create a fresh empty repo

1. Go to **https://github.com/new**
2. **Repository name:** `leadbot` (same name)
3. **Visibility:** `Private`
4. **DO NOT** tick anything else (no README, no gitignore, no license)
5. Click **"Create repository"**
6. You'll see a "Quick setup" page. **Leave it open.**

### Step 5: Drag-drop all the files

1. Open the unzipped `leadbot/` folder in your file manager
2. **Important:** select the *contents* of the `leadbot/` folder, not the folder itself
   - On Windows: open the folder, press Ctrl+A, then drag
   - On Mac: same, Cmd+A then drag
   - You should see files like `bot.py`, `INSTALL.md`, `requirements.txt`, `nixpacks.toml`, `mise.toml`, plus folders like `ai/`, `outreach/`, etc.
3. Drag them all into the GitHub "upload files" area
4. Wait until GitHub shows "50+ files" (it may take 10-30 seconds for the count to update)
5. Scroll down, type commit message: `fresh deploy`
6. Click **"Commit changes"**
7. Wait 1-2 minutes for all files to upload

### Step 6: Reconnect Railway

1. Go to **https://railway.app** → your project
2. Click the `leadbot` service
3. Click the **"Settings"** tab
4. Scroll to **"Source Repo"** (or **"GitHub"** section)
5. Click **"Disconnect"** then **"Connect to GitHub"**
6. Select your freshly-created `leadbot` repo
7. Railway will start a new deploy automatically

### Step 7: Verify env vars are still set

1. **Variables** tab
2. Check that all your previous env vars are still there (they should be — disconnecting the repo doesn't wipe them)
3. Add the new ones: `GMAIL_WEBHOOK_URL` and any others from the latest INSTALL.md
4. Done!

---

## Option B: One file at a time (when only 1-2 files changed)

**Best for:** small tweaks (changing a prompt, fixing a typo).

1. Go to the file in GitHub (e.g. `https://github.com/simalidudu-boop/leadbot/blob/main/bot.py`)
2. Click the **pencil icon** (✏️) at the top right
3. Select all (Ctrl+A) and delete
4. Open the new file on your computer in any text editor
5. Select all, copy
6. Paste into the GitHub editor
7. Scroll down, click **"Commit changes"**
8. Repeat for each file that changed

---

## Option C: Ask me for a per-file patch (medium effort)

**Best for:** when 2-5 files changed and Option A feels heavy.

Tell me which files you want updated. I'll paste the full new content
of each one in the chat. You open the file in GitHub, click pencil,
Ctrl+A → Delete → paste the new content → commit.

---

## How do I know which files changed?

Look at `/home/user/leadbot/` on the assistant's machine. Compare
against what's in your GitHub repo. Or just ask me:

> "which files are different from the last version?"

I'll list them and you choose Option A, B, or C.
