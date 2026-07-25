# AGENTS.md — operating guide for AI coding agents

You (the AI agent — Claude Code, Codex, Cursor, or similar) are helping a person set
up and run a **Goodreads giveaway auto-enter tool** (Python + Playwright) on THEIR
own machine, driving THEIR own logged-in Goodreads account. Read this whole file
before acting. If the user just pasted this repo's link and said "set this up," follow
**First-time setup** top to bottom.

> This needs a harness that can run local commands and a real browser on the user's
> machine (Claude Code, Codex CLI, Cursor, or the user running Python themselves).
> A browser-only assistant that can't execute local shell commands (e.g. ChatGPT in
> the web app) cannot run this — Playwright drives a real Chromium locally.

## What it does
Uses the user's saved Goodreads browser session to auto-enter **print** book giveaways
that match the genres THEY choose, at human pace, on a loop. A per-user dedupe log
(`entered.json`) means it never enters the same giveaway twice. Kindle giveaways use a
different entry flow (Amazon account linking) and are skipped — this tool is print-only.

## Golden rules — read before doing anything
1. **This drives the user's real account.** Goodreads' rules discourage automated
   entries; the mitigation is slow, human-like pacing. Don't parallelize or speed it up.
2. **Never commit personal data.** `browser-profile/` (the login), `config.yaml`, and
   `entered.json` are all gitignored and per-user. Don't add them to git.
3. **Only ONE machine runs it at a time per account.** Each machine keeps its own
   `entered.json`; two running at once would double-enter.
4. **Runs headed, never headless** — Goodreads blocks headless browsers.
5. **Print only — entries need a saved US shipping address** on the Goodreads account.
   If the user has no address, entries can't complete until they add one.

## First-time setup
Do these in order. Adapt the venv-activation command to the user's OS.

### 1. Install dependencies
Confirm Python 3.10+ is present (`python3 --version`); if not, help them install it.
Then, from the repo root:
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure — interview the user, then write config.yaml
Ask the user these two questions and record the answers. (You may instead run
`python giveaways.py setup`, which asks the same two interactively — but if your harness
can't type into an interactive prompt, just copy `config.example.yaml` to `config.yaml`
and edit the values yourself.)

1. **Which genres do you want to enter into?** Free-form list (e.g. "fantasy, science
   fiction, mystery"). A giveaway matches if any of its Goodreads genre tags contains
   any term (case-insensitive substring). **Blank = every genre.** → `include_genres`
2. **How many giveaways per session?** Recommend **999** (effectively "everything
   available"); let them lower it. → `run.max_per_sweep`

Write those into `config.yaml`. Leave `exclude_keywords`, `scan`, `pacing`, and
`run.live: false` at their template defaults. (This tool is print-only; there's no
format to choose — Kindle giveaways are skipped automatically.)

### 3. Log in (the user authenticates themselves)
```bash
python giveaways.py login
```
A real browser opens. **The user** signs in to Goodreads — either "Sign in with
Amazon" or a Goodreads email + password. You cannot and should not enter their
credentials; wait for them to confirm they're logged in, then the session saves to
`browser-profile/`. There is no password stored in the code.

### 4. Dry run, then go live
```bash
python giveaways.py scan            # preview matches; clicks nothing
python giveaways.py run             # DRY RUN: finds the Enter button, never clicks
python giveaways.py run --live --limit 3   # 3 real entries — verify they worked
python giveaways.py run --live      # full session (up to max_per_sweep)
```
Have the user watch a dry run and a small `--limit` live run pick correctly before
turning it loose.

## Optional: overnight loop
Re-runs the sweep so newly-posted giveaways get entered over time.
- macOS/Linux: `nohup caffeinate -i ./sweep_loop.sh > /dev/null 2>&1 &`
- Windows: `powershell -ExecutionPolicy Bypass -File .\sweep_loop.ps1`

## Config reference (`config.yaml`)
- `include_genres` — **allowlist**; empty = all genres.
- `exclude_keywords` — veto against title + blurb + genres; runs after the allowlist.
- `scan.start_urls` — keep `?sort=ending_soon` (the only sort that pages the full pool).
- `scan.max_clicks` — collection depth (~15 giveaways per click).
- `pacing.{min,max}_seconds` — delay between actions; keep it slow.
- `run.live` — master dry-run/live switch (`--live` overrides).
- `run.max_per_sweep` — max NEW entries per session (default 999; `--limit N` overrides).

## How it works (for maintenance)
- `collect_show_urls` — clicks "Show more giveaways" to page the list (Goodreads has no
  `?page=N`).
- `scrape_giveaway` — format from the giveaway page's `Format:` field; genres by hopping
  to the linked book page (`[data-testid='genresList']`).
- `is_interesting` — the gate: skip kindle, genre matches `include_genres` (empty = any),
  not vetoed by `exclude_keywords`.
- `enter_giveaway` / `_submit_entry` — flow is Enter Giveaway → Select address →
  `#termsCheckBox` → submit; kindle giveaways are skipped (`skipped_kindle`). Entered-state
  is detected via first-person markers ("you are entered", "edit entry info"), NEVER the
  "N people entered" facepile text.
- Each giveaway is wrapped in try/except so one flaky page never aborts a sweep.
