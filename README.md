# Goodreads giveaway auto-enter

Automates entering Goodreads giveaways that match filters you set, using your own
logged-in session. Human-paced, with a dry-run default and a dedupe log.

> ⚠️ Goodreads' giveaway rules discourage automated entries. This drives *your*
> account at slow, human-like pace, but you're accepting that risk. Keep pacing slow.

## One-time setup

```bash
cd ~/goodreads-giveaways
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python giveaways.py login          # log in once in the window that opens
```

## Daily use

```bash
source .venv/bin/activate
python giveaways.py scan           # see what matches your filters (never clicks)
python giveaways.py run            # dry run by default (finds Enter button, doesn't click)
python giveaways.py run --live     # actually enter matches
python giveaways.py run --live --limit 5   # cap it while you build trust
```

## Tuning

Everything lives in `config.yaml`: genres, keywords, formats, which listing pages
to scan, pagination depth, and pacing. Start with `scan`, adjust filters, repeat.

- `entered.json` — log of what's been entered, so nothing is entered twice.
- `browser-profile/` — your saved login. Never commit these (they're gitignored).

## How it works

1. `collect_show_urls` walks the listing pages and gathers giveaway links.
2. `scrape_giveaway` opens each one and reads title, genres, and format.
3. `is_interesting` applies the format gate + genre/keyword match from config.
4. `enter_giveaway` locates (and, when live, clicks) the Enter button.
