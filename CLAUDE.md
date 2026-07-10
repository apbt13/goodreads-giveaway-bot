# CLAUDE.md — operating guide

You (Claude) are helping run/maintain a **Goodreads giveaway auto-enter bot**
(Python + Playwright). Read this whole file before acting — it encodes gotchas that
are not obvious from the code. If the user just cloned this and wants it running,
jump to **Setup** then **Running**.

## What it does
Uses a saved Goodreads browser session to auto-enter **print** book giveaways that
pass a blocklist filter, at human pace, on a loop. A dedupe log means it never enters
the same giveaway twice.

## Golden rules — read before doing anything
1. **Only ONE machine runs it at a time.** Each machine keeps its own `entered.json`;
   running the Mac and the Windows PC together would double-enter. Make sure the other
   machine's loop is stopped first.
2. **`entered.json` is the dedupe log and is committed to the repo.** Never delete or
   reset it unless the user explicitly wants to re-enter everything from scratch.
3. **`browser-profile/` is per-machine and gitignored.** Every machine must run
   `python giveaways.py login` once. That saved session IS the login — there is no
   password in the code.
4. **Runs headed, never headless** — Goodreads blocks headless browsers.
5. **Print only; the Goodreads account needs a saved US shipping address** (print
   entries select an address). Kindle / children's / Christian / parenting are
   excluded by design.
6. **Keep pacing slow.** Goodreads' rules discourage automation; slow human-like
   pacing is the main mitigation. Don't parallelize or speed it up aggressively.

## Setup (fresh machine)
Windows (PowerShell) — annotated version in `WINDOWS.md`:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
python -m playwright install chromium
python giveaways.py login           # browser opens; sign in; press Enter
```
macOS/Linux: identical, but `source .venv/bin/activate`.

## Running
```
python giveaways.py scan                   # list matches; clicks nothing
python giveaways.py run                     # DRY RUN: finds Enter button, never clicks
python giveaways.py run --live              # actually enter matches
python giveaways.py run --live --limit 5    # cap entries (use when testing)
```
Overnight loop:
- Windows: `powershell -ExecutionPolicy Bypass -File .\sweep_loop.ps1`
- macOS:  `nohup caffeinate -i ./sweep_loop.sh >/dev/null 2>&1 &`

## Monitor / stop
- Count entered: `python -c "import json;print(len(json.load(open('entered.json'))))"`
- Live log: Windows `Get-Content .\sweep.log -Wait -Tail 30` · macOS `tail -f sweep.log`
- Stop loop: Windows `Get-Process python | Stop-Process` · macOS `pkill -f sweep_loop.sh`
- If a killed loop leaves Chromium locking the profile ("Opening in existing browser
  session"), clear it before relaunching: `pkill -f "user-data-dir=...browser-profile"`.

## Tuning — everything is in config.yaml
- `filters.exclude_genres` / `exclude_keywords` / `exclude_formats` — the blocklist.
- `scan.start_urls` — use `?sort=ending_soon`; it's the only list that pages the full
  ~1,600 pool (featured/default plateau at ~170). `scan.max_clicks` = collection depth
  (~15 giveaways per click).
- `run.max_per_sweep` — max new entries per sweep (0 = unlimited). `run.live` — master
  dry-run/live switch (a `--live` flag overrides it).
- `pacing` — seconds between actions.

## How it works (for maintenance)
- `collect_show_urls` — clicks "Show more giveaways" to page the list (NOT `?page=N`,
  which doesn't work).
- `scrape_giveaway` — format from the giveaway page's `Format:` field; genres by hopping
  to the book page (`[data-testid='genresList']`, not the giveaway page).
- `is_interesting` — the blocklist gate.
- `enter_giveaway` / `_submit_entry` — flow is Enter Giveaway → Select this address →
  `#termsCheckBox` → submit. Entered-state is detected via first-person `ENTERED_MARKERS`
  ("you are entered", "edit entry info"), NEVER the "N people entered this giveaway"
  facepile text (that false-positived early on).
- Each giveaway is wrapped in try/except so one flaky page never aborts a sweep;
  clicks use `no_wait_after=True` so slow navigations don't hang.
