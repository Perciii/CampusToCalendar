# CampusToCalendar

Automatically export your planned **Campus Coach** running workouts to a
standard `.ics` calendar file that you can import directly into **Google
Calendar** or **Apple Calendar**.

---

## How it works

The tool logs into the **Campus Coach web app** using your account
credentials, navigates to your weekly training plan, and extracts the title
and duration of every workout card.  It then writes a `.ics` file with one
calendar event per workout, which you import into Google Calendar in a single
click.

```
Campus Coach web app  →  scraper.py  →  workouts.ics  →  Google Calendar
```

---

## Requirements

- Python 3.10 or later
- A Campus Coach account (the same one you use on your iPhone)
- A desktop/laptop with internet access (the scraper runs on your computer,
  not on the phone)

Install all dependencies in one step:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

---

## Quick start

```bash
# 1 – set your credentials (recommended: use env vars so they stay out of
#     your shell history)
export CAMPUS_EMAIL="you@example.com"
export CAMPUS_PASSWORD="yourpassword"

# 2 – scrape the current week and write workouts.ics
python scraper.py -o workouts.ics

# 3 – import workouts.ics into Google Calendar
#     Settings → Import & Export → Import → choose workouts.ics
```

Each workout in the Campus Coach weekly plan becomes a calendar event with:
- the workout **title** (e.g. *Strength & Conditioning*)
- the prescribed **duration** (e.g. 30 min)

Events are created as **all-day events** spread across the week (Monday =
Workout 1, Tuesday = Workout 2, …).  You can drag them to any time slot you
like in Google Calendar.

---

## Scraper CLI reference

```
usage: scraper.py [-h] [--email EMAIL] [--password PASSWORD]
                  [--week YYYY-MM-DD] [-o OUTPUT] [--headed] [--dry-run]

options:
  --email EMAIL          Campus Coach e-mail (or set CAMPUS_EMAIL env var)
  --password PASSWORD    Campus Coach password (or set CAMPUS_PASSWORD env var)
  --week YYYY-MM-DD      Any date within the target week (default: current week)
  -o OUTPUT              Output ICS file path (default: workouts.ics)
  --headed               Show the browser window – useful for debugging
  --dry-run              Print scraped workouts as JSON and exit without writing
                         an ICS file
```

### Scraping a specific week

```bash
python scraper.py --week 2024-06-10 -o week24.ics
```

### Debugging when the scraper fails

Run with `--headed` to see exactly what the browser is doing:

```bash
python scraper.py --headed
```

If the CSS selectors stop matching after a Campus Coach UI update, open
`scraper.py` and look for the `SELECTORS` dict near the top of the file.
Each selector is documented and can be updated independently.

---

## Importing into Google Calendar

1. Open [Google Calendar](https://calendar.google.com) on your computer.
2. Click the ⚙ gear icon → **Settings**.
3. In the left panel click **Import & Export**.
4. Click **Import**, choose the `.ics` file, and click **Import**.

For **Apple Calendar**: **File → Import…** → choose the `.ics` file.

---

## Running the tests

```bash
pip install pytest
python -m pytest tests/ -v
```

The tests cover all pure-Python logic (duration parsing, date assignment,
workout extraction) without requiring a real browser or a Campus Coach account.

---

## Project layout

```
CampusToCalendar/
├── scraper.py              # Playwright-based Campus Coach scraper  ← main tool
├── campus_to_calendar.py   # CSV/JSON → ICS converter (used by scraper)
├── requirements.txt
├── sample_data/
│   ├── workouts.csv        # Sample CSV for manual entry
│   └── workouts.json       # Sample JSON for manual entry
└── tests/
    ├── test_scraper.py
    └── test_campus_to_calendar.py
```

---

## Manual fallback (CSV / JSON)

If automatic scraping is not working, you can still create the ICS file
manually by filling in a CSV or JSON file:

```bash
python campus_to_calendar.py sample_data/workouts.csv -o workouts.ics
```

See `sample_data/workouts.csv` for the column format.

