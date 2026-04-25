# CampusToCalendar

Export your planned **Campus Coach** running workouts to a standard `.ics`
calendar file that can be imported into **Google Calendar**, **Apple
Calendar**, or any other iCalendar-compatible app.

---

## Features

- Reads planned workout data from a **CSV** or **JSON** file
- Creates one calendar event per workout containing:
  - **Name** / title
  - **Date and start time**
  - **Planned duration**
  - **Planned distance** (km) – optional
  - **Elevation gain** (m) – optional
  - **Notes** – optional
- Rows with missing required fields are skipped with a warning rather
  than aborting the whole export
- Output is a standards-compliant `.ics` file (RFC 5545)

---

## Requirements

- Python 3.10+
- [`icalendar`](https://pypi.org/project/icalendar/) library

Install the dependency:

```bash
pip install -r requirements.txt
```

---

## Quick start

```bash
# Export from CSV
python campus_to_calendar.py sample_data/workouts.csv -o workouts.ics

# Export from JSON
python campus_to_calendar.py sample_data/workouts.json -o workouts.ics
```

Then import `workouts.ics` into your calendar:

- **Google Calendar** → Settings → Import & Export → Import
- **Apple Calendar** → File → Import…

---

## Input format

### CSV

The first row must be a header. Column names:

| Column | Required | Description |
|---|---|---|
| `name` | ✅ | Workout title (e.g. *Easy Run*) |
| `date` | ✅ | Planned date — `YYYY-MM-DD` |
| `duration_minutes` | ✅ | Planned duration in minutes |
| `time` | | Start time — `HH:MM` (default: `09:00`) |
| `distance_km` | | Planned distance in kilometres |
| `elevation_m` | | Planned elevation gain in metres |
| `notes` | | Free-text notes |

Example (`sample_data/workouts.csv`):

```csv
name,date,time,duration_minutes,distance_km,elevation_m,notes
Easy Run,2024-06-03,07:30,45,8.0,50,Keep heart rate under 140 bpm
Interval Training,2024-06-05,07:00,60,10.0,30,6x800m at 5K pace with 90s recovery
Long Run,2024-06-08,08:00,90,16.0,120,Steady aerobic pace throughout
```

### JSON

A JSON array of objects using the same field names as the CSV columns.

Example (`sample_data/workouts.json`):

```json
[
  {
    "name": "Easy Run",
    "date": "2024-06-03",
    "time": "07:30",
    "duration_minutes": 45,
    "distance_km": 8.0,
    "elevation_m": 50,
    "notes": "Keep heart rate under 140 bpm"
  }
]
```

---

## CLI reference

```
usage: campus_to_calendar.py [-h] [-o OUTPUT] [-f {csv,json}] input

positional arguments:
  input                 Path to the input file (CSV or JSON)

options:
  -h, --help            Show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path for the output ICS file (default: workouts.ics)
  -f {csv,json}, --format {csv,json}
                        Input format — auto-detected from file extension when
                        not specified
```

---

## How to get your planned workouts from Campus Coach

Campus Coach does not currently offer a direct calendar export.  The easiest
workflow is:

1. Open the Campus Coach app and browse your planned training programme.
2. Create a CSV or JSON file following the format above, entering one row
   per planned session.
3. Run the script and import the resulting `.ics` file into Google Calendar
   or Apple Calendar.

---

## Running the tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Project layout

```
CampusToCalendar/
├── campus_to_calendar.py   # Main conversion script
├── requirements.txt
├── sample_data/
│   ├── workouts.csv        # Sample CSV input
│   └── workouts.json       # Sample JSON input
└── tests/
    └── test_campus_to_calendar.py
```
