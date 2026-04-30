#!/usr/bin/env python3
"""
scraper.py – Log into the Campus Coach web app, scrape planned workouts, and
export them as an ICS file importable into Google Calendar or Apple Calendar.

Usage
-----
Set your Campus Coach credentials as environment variables (recommended):

    export CAMPUS_EMAIL="you@example.com"
    export CAMPUS_PASSWORD="yourpassword"
    python scraper.py -o workouts.ics

Or pass them directly (less secure – they appear in your shell history):

    python scraper.py --email you@example.com --password yourpassword -o workouts.ics

By default the scraper targets the current ISO week. Use --week to choose a
different week:

    python scraper.py --week 2024-06-03   # week containing 3 June 2024

Run with --headed to watch the browser navigate the site (useful for
debugging when selectors stop matching after a Campus Coach UI update):

    python scraper.py --headed

How dates are assigned
----------------------
Campus Coach's weekly plan lists workouts in order ("Workout 1 of 8",
"Workout 2 of 8", …) without pinning each one to a specific day.  The
scraper spreads them across the week starting on Monday: Workout 1 → Monday,
Workout 2 → Tuesday, etc.  If there are more workouts than days in the week,
they wrap into the next week.  All events are created as all-day events so
you can drag them to whatever time slot suits you in Google Calendar.

Customising selectors
---------------------
If a Campus Coach UI update breaks the scraper, open `scraper.py` and look
for the SELECTORS dict near the top of the file.  Run with --headed and
--dry-run to inspect what the browser sees without writing any files.
"""

import argparse
import os
import re
import sys
from datetime import date, timedelta

# Lazy import so the module can be imported in tests without a browser install.
try:
    from playwright.sync_api import Page, sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

from campus_to_calendar import create_calendar

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://app.campuscoach.app"

# CSS selectors / text patterns – update here if the Campus Coach UI changes.
SELECTORS = {
    # Login page
    "email_input":     'input[type="email"], input[name="email"], #email',
    "password_input":  'input[type="password"], input[name="password"], #password',
    "submit_button":   'button[type="submit"], input[type="submit"]',

    # Post-login navigation to the workouts/training tab
    "workouts_nav":    'a[href*="workout"], a[href*="training"], '
                       'nav a:has-text("Workout"), nav a:has-text("Training")',

    # Weekly plan page – header showing the date range
    "week_header":     'text=/\\d+ [a-zA-Zé]+ - \\d+ [a-zA-Zé]+/',

    # Each workout card on the weekly plan page
    "workout_card":    '[class*="workout"], [class*="session"], [class*="card"]',

    # Within each card: title and duration
    "card_title":      'h2, h3, [class*="title"], [class*="name"], strong',
    "card_duration":   '[class*="duration"], text=/\\d+\\s*min/i',
}

# Pattern that matches duration text like "30 min", "1h30", "1 h 30 min".
_DURATION_RE = re.compile(
    r"(?:(\d+)\s*h(?:eure?s?)?\s*)?(\d+)\s*min"  # "30 min", "1h 30 min"
    r"|(\d+)\s*h(?:eure?s?)?\s*(\d{1,2})\b",      # "1h30", "1 h 30" (no "min")
    re.IGNORECASE,
)
_DURATION_HOURS_ONLY_RE = re.compile(r"^(\d+)\s*h(?:eure?s?)?$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

def parse_duration_minutes(text: str) -> int | None:
    """
    Extract a duration in minutes from a human-readable string.

    Handles:
      "30 min", "50 min", "1h30", "1 h 30 min", "1 heure 30 min", "90 min"

    Returns None if no recognisable pattern is found.
    """
    text = text.strip()
    m = _DURATION_RE.search(text)
    if m:
        if m.group(1) is not None or m.group(2) is not None:
            # Matched "Nh Nmin" or plain "N min"
            hours = int(m.group(1) or 0)
            mins = int(m.group(2))
        else:
            # Matched compact "1h30" (groups 3 and 4)
            hours = int(m.group(3))
            mins = int(m.group(4))
        return hours * 60 + mins
    m2 = _DURATION_HOURS_ONLY_RE.search(text)
    if m2:
        return int(m2.group(1)) * 60
    return None


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def monday_of_week(ref: date) -> date:
    """Return the Monday of the ISO week that contains *ref*."""
    return ref - timedelta(days=ref.weekday())


def dates_for_workouts(week_start: date, count: int) -> list[date]:
    """
    Return *count* consecutive dates starting on *week_start* (Monday).

    Workouts wrap into subsequent weeks if count > 7.
    """
    return [week_start + timedelta(days=i) for i in range(count)]


# ---------------------------------------------------------------------------
# HTML / page parsing helpers (testable without a real browser)
# ---------------------------------------------------------------------------

def extract_workouts_from_cards(
    cards: list[dict],
    week_start: date,
) -> list[dict]:
    """
    Convert a list of raw card dicts (keys: ``title``, ``duration_text``)
    into a list of workout dicts compatible with ``campus_to_calendar.create_calendar``.

    Each workout is assigned to a consecutive day starting on *week_start*.
    Workouts with no parseable duration are skipped with a warning.
    """
    result = []
    day_offset = 0
    for i, card in enumerate(cards, start=1):
        title = (card.get("title") or "").strip()
        duration_text = (card.get("duration_text") or "").strip()

        if not title:
            print(f"  Warning: card {i} has no title – skipping.", file=sys.stderr)
            continue

        duration_minutes = parse_duration_minutes(duration_text) if duration_text else None
        if duration_minutes is None:
            print(
                f"  Warning: could not parse duration from '{duration_text}' "
                f"for workout '{title}' – skipping.",
                file=sys.stderr,
            )
            continue

        workout_date = week_start + timedelta(days=day_offset)
        result.append(
            {
                "name": title,
                "date": workout_date.isoformat(),
                "duration_minutes": duration_minutes,
            }
        )
        day_offset += 1

    return result


# ---------------------------------------------------------------------------
# Browser automation
# ---------------------------------------------------------------------------

def _login(page: "Page", email: str, password: str) -> None:
    """Navigate to the login page and authenticate."""
    page.goto(f"{BASE_URL}/login", timeout=30_000)
    # Some SPAs redirect / render asynchronously – wait for the email input.
    page.wait_for_selector(SELECTORS["email_input"], timeout=15_000)
    page.fill(SELECTORS["email_input"], email)
    page.fill(SELECTORS["password_input"], password)
    page.click(SELECTORS["submit_button"])
    # Wait until navigation away from the login page.
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def _navigate_to_week(page: "Page", week_start: date) -> None:
    """Navigate to the training-plan page for the week containing *week_start*."""
    # Try a direct URL first; many SPAs accept a date query parameter.
    target = f"{BASE_URL}/workouts?week={week_start.isoformat()}"
    page.goto(target, timeout=20_000)

    # If the page landed on a 404 / redirect, try the nav link fallback.
    try:
        page.wait_for_selector(SELECTORS["week_header"], timeout=8_000)
    except Exception:
        # Try clicking the Workouts navigation link instead.
        nav = page.query_selector(SELECTORS["workouts_nav"])
        if nav:
            nav.click()
            page.wait_for_load_state("networkidle", timeout=15_000)


def _scrape_cards(page: "Page") -> list[dict]:
    """
    Return a list of raw card dicts from the current page.

    Each dict has keys: ``title``, ``duration_text``.
    """
    page.wait_for_load_state("networkidle", timeout=15_000)
    cards_els = page.query_selector_all(SELECTORS["workout_card"])
    results = []
    for card_el in cards_els:
        # --- title ---
        title_el = card_el.query_selector(SELECTORS["card_title"])
        title = (title_el.inner_text() if title_el else "").strip()

        # --- duration ---
        # First try a dedicated duration element…
        dur_el = card_el.query_selector(SELECTORS["card_duration"])
        if dur_el:
            duration_text = dur_el.inner_text().strip()
        else:
            # …fall back to searching the full card text for a duration pattern.
            card_text = card_el.inner_text()
            m = _DURATION_RE.search(card_text)
            duration_text = m.group(0) if m else ""

        if title or duration_text:
            results.append({"title": title, "duration_text": duration_text})

    return results


def scrape(
    email: str,
    password: str,
    week_start: date,
    headed: bool = False,
) -> list[dict]:
    """
    Log in, navigate to *week_start*'s training plan, and return a list of
    workout dicts ready for :func:`campus_to_calendar.create_calendar`.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "playwright is not installed.  Run: pip install playwright && "
            "python -m playwright install chromium"
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        context = browser.new_context(locale="fr-FR")
        page = context.new_page()

        try:
            _login(page, email, password)
            _navigate_to_week(page, week_start)
            raw_cards = _scrape_cards(page)
        finally:
            browser.close()

    print(f"Found {len(raw_cards)} workout card(s) on the page.", file=sys.stderr)
    return extract_workouts_from_cards(raw_cards, week_start)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape planned workouts from the Campus Coach web app and "
            "export them as an ICS calendar file.\n\n"
            "Set CAMPUS_EMAIL and CAMPUS_PASSWORD environment variables "
            "before running."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("CAMPUS_EMAIL"),
        help="Campus Coach account e-mail (or set CAMPUS_EMAIL env var).",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("CAMPUS_PASSWORD"),
        help="Campus Coach account password (or set CAMPUS_PASSWORD env var).",
    )
    parser.add_argument(
        "--week",
        metavar="YYYY-MM-DD",
        help=(
            "Any date within the target week (default: current week). "
            "The Monday of that week is used as the first workout date."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default="workouts.ics",
        help="Path for the output ICS file (default: workouts.ics).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window (useful for debugging).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the scraped workouts to stdout and exit without "
            "writing an ICS file."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # --- validate credentials ---
    if not args.email:
        print(
            "Error: Campus Coach e-mail not provided.\n"
            "Set the CAMPUS_EMAIL environment variable or use --email.",
            file=sys.stderr,
        )
        return 1
    if not args.password:
        print(
            "Error: Campus Coach password not provided.\n"
            "Set the CAMPUS_PASSWORD environment variable or use --password.",
            file=sys.stderr,
        )
        return 1

    # --- resolve target week ---
    if args.week:
        try:
            ref = date.fromisoformat(args.week)
        except ValueError:
            print(
                f"Error: --week must be a date in YYYY-MM-DD format, got '{args.week}'.",
                file=sys.stderr,
            )
            return 1
    else:
        ref = date.today()

    week_start = monday_of_week(ref)
    print(f"Targeting week: {week_start} – {week_start + timedelta(days=6)}", file=sys.stderr)

    # --- scrape ---
    try:
        workouts = scrape(
            email=args.email,
            password=args.password,
            week_start=week_start,
            headed=args.headed,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error while scraping Campus Coach: {exc}", file=sys.stderr)
        if not args.headed:
            print(
                "Tip: re-run with --headed to watch the browser and diagnose "
                "the problem.",
                file=sys.stderr,
            )
        return 1

    if not workouts:
        print(
            "No workouts were found for that week.  "
            "Try --headed to inspect the page.",
            file=sys.stderr,
        )
        return 1

    # --- dry-run ---
    if args.dry_run:
        import json
        print(json.dumps(workouts, indent=2, ensure_ascii=False))
        return 0

    # --- write ICS ---
    try:
        cal = create_calendar(workouts)
    except ValueError as exc:
        print(f"Error building calendar: {exc}", file=sys.stderr)
        return 1

    try:
        with open(args.output, "wb") as fh:
            fh.write(cal.to_ical())
    except OSError as exc:
        print(f"Error writing '{args.output}': {exc}", file=sys.stderr)
        return 1

    event_count = sum(1 for c in cal.walk() if c.name == "VEVENT")
    print(
        f"Created '{args.output}' with {event_count} workout event(s).\n"
        "Import this file into Google Calendar or Apple Calendar."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
