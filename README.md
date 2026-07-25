# Goodreads giveaway auto-enter

Automatically enters Goodreads **print** book giveaways in the genres **you** choose,
using your own logged-in session. Human-paced, with a dry-run default and a per-user
dedupe log so nothing is entered twice.

> ⚠️ Goodreads' giveaway rules discourage automated entries. This drives *your* account
> at slow, human-like pace, but you're accepting that risk. Keep pacing slow. Only run
> one machine per account at a time.

## Two ways to run it

**A. Hand the repo to your AI coding agent.** Paste this repo's link into a local agent
harness (Claude Code, Codex CLI, Cursor, etc.) and say *"set this up for me."* The agent
reads [`AGENTS.md`](AGENTS.md), installs the dependencies, asks you which genres you want
and how many to enter, then walks you through logging in.

> This needs a harness that can run local commands and open a real browser on your
> machine. A browser-only chatbot that can't execute shell commands (e.g. ChatGPT in the
> web app) **can't** run this — it uses Playwright to drive a real Chromium locally.

**B. Run it yourself.** Four commands:

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium

python giveaways.py setup     # pick genres and how many per session
python giveaways.py login     # sign in once (Amazon, or Goodreads email + password)
python giveaways.py scan      # preview what matches (clicks nothing)
python giveaways.py run       # dry run; add --live to actually enter
```

This tool enters **print** giveaways only — you'll need a saved US shipping address on
your Goodreads account. (Kindle giveaways use a separate Amazon-linked flow and are
skipped automatically.) Setup asks:
- **Genres** — which genres to enter into (e.g. `fantasy, science fiction`). Leave blank
  to enter every genre.
- **Per session** — how many to enter at once. Default **999** (effectively "everything
  available"); lower it while you build trust.

## Daily use

```bash
source .venv/bin/activate
python giveaways.py scan               # see what matches (never clicks)
python giveaways.py run                # dry run by default
python giveaways.py run --live         # actually enter matches
python giveaways.py run --live --limit 5   # cap it while you build trust
```

Overnight loop (re-sweeps for newly-posted giveaways):
- macOS/Linux: `nohup caffeinate -i ./sweep_loop.sh > /dev/null 2>&1 &`
- Windows: `powershell -ExecutionPolicy Bypass -File .\sweep_loop.ps1`  (see [WINDOWS.md](WINDOWS.md))

## Files
- `config.yaml` — your settings, created by `setup` (gitignored; template is
  `config.example.yaml`).
- `entered.json` — your personal dedupe log, so nothing is entered twice (gitignored;
  created on first run).
- `browser-profile/` — your saved login (gitignored; created by `login`).

## How it works
1. `collect_show_urls` walks the listing pages and gathers giveaway links.
2. `scrape_giveaway` opens each one and reads title, genres, and format.
3. `is_interesting` keeps the print ones whose genre matches your config.
4. `enter_giveaway` locates (and, when `--live`, clicks) the Enter button.
