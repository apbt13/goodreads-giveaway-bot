#!/usr/bin/env python3
"""
Goodreads giveaway auto-enter.

Commands:
  python giveaways.py login    Open a browser so you can log in once. The session
                               is saved to ./browser-profile and reused after that.
  python giveaways.py scan     Scrape + filter giveaways and print what matches.
                               Never clicks anything. Use this to tune config.yaml.
  python giveaways.py run      Scrape + filter, then ENTER matching giveaways.
                               Honors run.live in config.yaml (dry run unless true).

Flags:
  --live         Force real entering for this run (overrides config).
  --dry-run      Force dry run for this run (overrides config).
  --headless     Run without a visible window (not recommended while tuning).
  --limit N      Stop after N matching giveaways this run.

This automates YOUR logged-in account at human pace. Goodreads' rules discourage
automated entries; you're accepting that risk knowingly. Keep pacing slow.
"""

import argparse
import json
import os
import random
import re
import sys
import time

import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(HERE, "browser-profile")
CONFIG_PATH = os.path.join(HERE, "config.yaml")
ENTERED_PATH = os.path.join(HERE, "entered.json")

SHOW_RE = re.compile(r"/giveaway/show/(\d+)")

# First-person markers Goodreads shows once YOU have entered a giveaway. Note:
# NOT "entered this giveaway" — that appears in the "N people entered" facepile.
ENTERED_MARKERS = ("you are entered", "you have entered", "edit entry info",
                   "you're entered")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_entered():
    if os.path.exists(ENTERED_PATH):
        with open(ENTERED_PATH) as f:
            return json.load(f)
    return {}


def save_entered(entered):
    with open(ENTERED_PATH, "w") as f:
        json.dump(entered, f, indent=2, sort_keys=True)


def human_pause(cfg):
    lo = cfg["pacing"]["min_seconds"]
    hi = cfg["pacing"]["max_seconds"]
    time.sleep(random.uniform(lo, hi))


def giveaway_id(url):
    m = SHOW_RE.search(url)
    return m.group(1) if m else None


# --------------------------------------------------------------------------- #
# scraping
# --------------------------------------------------------------------------- #
def _harvest_links(page, found):
    """Add every currently-rendered /giveaway/show/ link to `found` (keyed by id).
    Each giveaway renders two links (cover + title), so we de-dupe by id."""
    hrefs = page.eval_on_selector_all(
        "a[href*='/giveaway/show/']", "els => els.map(e => e.href)"
    )
    gained = 0
    for h in hrefs:
        gid = giveaway_id(h)
        if gid and gid not in found:
            found[gid] = h.split("?")[0]
            gained += 1
    return gained


def collect_show_urls(page, start_urls, max_clicks, cap):
    """Gather unique giveaway URLs by repeatedly clicking "Show more giveaways".

    Goodreads shows ~15 giveaways at a time behind a client-side "Show more"
    button (no URL pagination). We click it until the button is gone, no new
    giveaways appear, we've clicked max_clicks times, or we hit the cap.
    """
    found = {}
    show_more = re.compile(r"show more giveaways", re.I)
    for base in start_urls:
        try:
            page.goto(base, wait_until="domcontentloaded", timeout=30000)
        except PWTimeout:
            print(f"  ! timeout loading {base}")
            continue
        page.wait_for_timeout(1500)
        clicks, stagnant = 0, 0
        while clicks < max_clicks and len(found) < cap:
            _harvest_links(page, found)
            btn = page.get_by_role("button", name=show_more)
            if btn.count() == 0 or not btn.first.is_visible():
                break
            try:
                btn.first.scroll_into_view_if_needed()
                btn.first.click()
            except Exception:
                break
            clicks += 1
            page.wait_for_timeout(2500)  # give the lazy load time to render
            gained = _harvest_links(page, found)
            stagnant = stagnant + 1 if gained == 0 else 0
            if stagnant >= 3:  # three dead clicks in a row -> end of this list
                break
        print(f"  {base.split('//')[-1][:38]}: {len(found)} giveaways "
              f"after {clicks} 'show more' clicks")
        if len(found) >= cap:
            break
    return dict(list(found.items())[:cap])


GENRES_SEL = "[data-testid='genresList'] a[href*='/genres/']"


def scrape_giveaway(page, url):
    """Open a giveaway page and pull the bits we filter on.

    Format comes from the giveaway page's own "Format:" field. Genres are NOT on
    the giveaway page, so we hop to the linked book page (in a second tab) to read
    them, then close it — leaving `page` on the giveaway so entering still works.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def meta(prop):
        el = page.query_selector(f"meta[property='{prop}']")
        return el.get_attribute("content") if el else ""

    title = meta("og:title") or (page.title() or "")
    description = meta("og:description") or ""  # clean blurb for keyword matching

    # format: read the giveaway's own "Format:" detail line
    fmt = "unknown"
    for p in page.query_selector_all("p.giveawayDetailItem"):
        t = p.inner_text()
        if "Format:" in t:
            val = t.split(":", 1)[1].strip().lower()
            fmt = "kindle" if ("kindle" in val or "ebook" in val) else (
                "print" if "print" in val else val)
            break

    # genres: open the linked book page in a throwaway tab
    genres = []
    book_el = page.query_selector("a[href*='/book/show/']")
    if book_el:
        book_url = book_el.evaluate("e => e.href")  # resolved absolute URL
        bp = page.context.new_page()
        try:
            bp.goto(book_url, wait_until="domcontentloaded", timeout=30000)
            try:
                bp.wait_for_selector(GENRES_SEL, timeout=8000)
            except PWTimeout:
                pass  # some books simply have no genre tags
            genres = bp.eval_on_selector_all(
                GENRES_SEL, "els => els.map(e => e.textContent.trim())"
            )
            genres = [g for g in dict.fromkeys(genres) if g]
        finally:
            bp.close()

    return {
        "url": url,
        "title": title.strip(),
        "description": description.strip(),
        "genres": genres,
        "format": fmt,
    }


# --------------------------------------------------------------------------- #
# filtering
# --------------------------------------------------------------------------- #
def is_interesting(g, filters):
    """Blocklist model: enter everything EXCEPT excluded formats/genres/keywords."""
    ex_formats = [s.lower() for s in (filters.get("exclude_formats") or [])]
    if g["format"] in ex_formats:
        return False, f"excluded format: {g['format']}"

    ex_genres = [s.lower() for s in (filters.get("exclude_genres") or [])]
    genre_blob = " ".join(g["genres"]).lower()
    for term in ex_genres:
        if term in genre_blob:
            return False, f"excluded genre (~{term})"

    # keywords match title + blurb only (not the whole page's chrome).
    ex_keywords = [s.lower() for s in (filters.get("exclude_keywords") or [])]
    text_blob = (g["title"] + " " + g.get("description", "")).lower()
    for term in ex_keywords:
        if term in text_blob:
            return False, f"excluded keyword (~{term})"

    return True, "not excluded"


# --------------------------------------------------------------------------- #
# entering
# --------------------------------------------------------------------------- #
def find_enter_button(page):
    """Return a locator for the Enter Giveaway control, or None."""
    pat = re.compile(r"enter giveaway", re.I)
    for getter in (
        lambda: page.get_by_role("button", name=pat),
        lambda: page.get_by_role("link", name=pat),
    ):
        loc = getter()
        if loc.count() > 0:
            return loc.first
    # fallback: a submit input whose value mentions Enter
    loc = page.locator("input[type='submit'][value*='Enter' i]")
    if loc.count() > 0:
        return loc.first
    return None


def enter_giveaway(page, cfg, dry_run):
    """Attempt to enter the giveaway currently loaded. Returns (status, note).

    Print flow: the "Enter Giveaway" link navigates to an address page. If the
    account has no saved shipping address, entry is impossible until one is added.
    The final submit-on-address-page step is wired up in _submit_entry() once we've
    confirmed its markup against a real account-with-address.
    """
    # The Enter button is the reliable signal. Its presence means "not yet
    # entered". (Do NOT sniff body text for "entered this giveaway" — that phrase
    # appears in the "N people entered this giveaway" facepile on every page.)
    btn = find_enter_button(page)
    if btn is None:
        body_low = page.inner_text("body").lower()
        if any(s in body_low for s in ENTERED_MARKERS):
            return "already", "already entered on Goodreads"
        return "no_button", "no Enter button (ended / not eligible)"

    if dry_run:
        return "would", "Enter button located (dry run — not clicked)"

    btn.scroll_into_view_if_needed()
    human_pause(cfg)
    btn.click(no_wait_after=True)  # don't block on the ensuing navigation
    _settle(page)
    return _submit_entry(page, cfg)


def _settle(page, ms=1000):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PWTimeout:
        pass
    page.wait_for_timeout(ms)


def _submit_entry(page, cfg):
    """Finish a print entry:  address page -> terms page -> submit.

    Only ever touches the giveaway's own terms checkbox (#termsCheckBox) and the
    final "Enter Giveaway" submit — never the favorite-genre preference boxes.
    """
    # Kindle giveaways use a different flow and are excluded by policy. If format
    # detection missed one (no clean "Format:" field), we still bail here rather
    # than enter it. Clicking Enter only navigated here — it did not enter you.
    if "enter_kindle_giveaway" in page.url:
        return "skipped_kindle", "Kindle giveaway — skipped (slipped the format gate)"

    # Step: address chooser -> "Select this address"
    if "enter_choose_address" in page.url:
        pick = page.get_by_role("link", name=re.compile(r"select this address", re.I))
        if pick.count() == 0:
            return "needs_address", "no saved shipping address to select"
        human_pause(cfg)
        pick.first.click(no_wait_after=True)
        _settle(page)

    # Step: terms page -> tick terms, submit
    terms = page.locator("#termsCheckBox")
    if terms.count() == 0:
        terms = page.locator("input[name='entry_terms']")
    try:
        if terms.count() and not terms.first.is_checked():
            terms.first.check()
    except Exception as e:
        return "maybe", f"couldn't tick terms box: {e}"

    submit = page.locator("input[type='submit'][value*='Enter' i]")
    if submit.count() == 0:
        submit = page.get_by_role("button", name=re.compile(r"enter giveaway", re.I))
    if submit.count() == 0:
        return "maybe", f"no final submit on {page.url}"

    human_pause(cfg)
    submit.first.click(no_wait_after=True)
    _settle(page, ms=1500)

    b = page.inner_text("body").lower()
    if any(s in b for s in ENTERED_MARKERS):
        return "entered", "confirmed entered"
    return "maybe", f"submitted; landed on {page.url} — please verify"


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_login(args):
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, viewport={"width": 1280, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.goodreads.com/user/sign_in")
        print("\nA browser opened. Log in to Goodreads (via Amazon) in that window.")
        print("When you can see your logged-in Goodreads home page, come back here")
        input("and press ENTER to save the session… ")
        ctx.close()
        print("Session saved to browser-profile/. You won't need to log in again.")


def _open_context(pw, headless):
    return pw.chromium.launch_persistent_context(
        PROFILE_DIR, headless=headless, viewport={"width": 1280, "height": 900}
    )


def cmd_scan(args):
    cfg = load_config()
    with sync_playwright() as pw:
        ctx = _open_context(pw, args.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print("Collecting giveaway links…")
        urls = collect_show_urls(
            page,
            cfg["scan"]["start_urls"],
            cfg["scan"]["max_clicks"],
            cfg["scan"]["max_giveaways"],
        )
        print(f"Found {len(urls)} giveaways. Scraping + filtering…\n")
        matches = []
        for gid, url in urls.items():
            try:
                g = scrape_giveaway(page, url)
            except Exception as e:
                print(f"  ! {url}: {e}")
                continue
            ok, why = is_interesting(g, cfg["filters"])
            flag = "MATCH " if ok else "  skip"
            gtxt = ", ".join(g["genres"][:4]) if g["genres"] else "— none scraped —"
            title = g["title"].replace("Book giveaway for ", "")
            print(f"{flag} [{g['format']:>7}] {title[:46]:46}  ({why})")
            print(f"        genres: {gtxt}")
            if ok:
                matches.append((gid, url, g["title"]))
            human_pause(cfg)
        print(f"\n{len(matches)} interesting giveaway(s).")
        ctx.close()


def cmd_run(args):
    cfg = load_config()
    dry_run = cfg["run"]["live"] is not True
    if args.live:
        dry_run = False
    if args.dry_run:
        dry_run = True
    limit = args.limit or cfg["run"].get("max_per_sweep", 0)
    entered = load_entered()

    mode = "DRY RUN (nothing will be clicked)" if dry_run else "LIVE — will enter"
    print(f"Mode: {mode}\n")

    with sync_playwright() as pw:
        ctx = _open_context(pw, args.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        urls = collect_show_urls(
            page,
            cfg["scan"]["start_urls"],
            cfg["scan"]["max_clicks"],
            cfg["scan"]["max_giveaways"],
        )
        print(f"Found {len(urls)} giveaways.\n")
        did = 0
        for gid, url in urls.items():
            if gid in entered:
                continue
            # One flaky page must never abort the sweep: catch everything, skip,
            # and keep going. scrape + filter + enter are all inside the guard.
            try:
                g = scrape_giveaway(page, url)
                ok, why = is_interesting(g, cfg["filters"])
                if not ok:
                    continue
                status, note = enter_giveaway(page, cfg, dry_run)
            except Exception as e:
                first = str(e).splitlines()[0] if str(e) else ""
                print(f"  ! skip {url.split('/show/')[-1][:30]}: "
                      f"{type(e).__name__}: {first[:70]}")
                continue
            print(f"[{status:>9}] {g['title'][:55]:55} — {note}")
            if status in ("entered", "already", "skipped_kindle"):
                entered[gid] = {"title": g["title"], "url": url, "status": status}
                save_entered(entered)
            # only real new entries (or dry-run matches) count toward the limit;
            # already-entered books are logged and skipped without burning it.
            if status in ("entered", "would"):
                did += 1
            if limit and did >= limit:
                print(f"\nHit limit of {limit}.")
                break
            human_pause(cfg)
        print(f"\nDone. {did} giveaway(s) {'matched' if dry_run else 'processed'}.")
        ctx.close()


def main():
    p = argparse.ArgumentParser(description="Goodreads giveaway auto-enter")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="Log in once; save the browser session")

    ps = sub.add_parser("scan", help="Scrape + filter, print matches (never clicks)")
    ps.add_argument("--headless", action="store_true")

    pr = sub.add_parser("run", help="Scrape + filter, then enter matches")
    pr.add_argument("--live", action="store_true", help="force real entering")
    pr.add_argument("--dry-run", action="store_true", help="force dry run")
    pr.add_argument("--headless", action="store_true")
    pr.add_argument("--limit", type=int, default=0)

    args = p.parse_args()
    if not os.path.exists(PROFILE_DIR) and args.cmd != "login":
        print("No saved session yet. Run:  python giveaways.py login")
        sys.exit(1)

    {"login": cmd_login, "scan": cmd_scan, "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    main()
