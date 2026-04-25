#!/usr/bin/env python3
"""
CampusToCalendar – Export Campus Coach planned workouts to ICS calendar format.

Reads workout data from a CSV or JSON file and writes an ICS file that can be
imported into Google Calendar, Apple Calendar, or any other iCalendar-compatible
application.

CSV column reference (JSON uses the same field names as object keys):
    name              – Workout name / title (required)
    date              – Planned date, YYYY-MM-DD (required)
    time              – Planned start time, HH:MM (optional, default: 09:00)
    duration_minutes  – Planned duration in minutes (required)
    distance_km       – Planned distance in kilometres (optional)
    elevation_m       – Planned elevation gain in metres (optional)
    notes             – Free-text notes (optional)

Usage:
    python campus_to_calendar.py workouts.csv -o workouts.ics
    python campus_to_calendar.py workouts.json -o workouts.ics
"""

import argparse
import csv
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

from icalendar import Calendar, Event


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_float(value: str | None) -> float | None:
    """Return a float from *value*, or None when the value is absent / invalid."""
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    """Return a timezone-aware datetime from date and optional time strings."""
    date_str = date_str.strip()
    time_str = (time_str or "09:00").strip() or "09:00"
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError(
            f"Cannot parse date '{date_str}' or time '{time_str}'. "
            "Expected YYYY-MM-DD and HH:MM."
        ) from exc
    return dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Input parsers
# ---------------------------------------------------------------------------

def parse_csv(filepath: str) -> list[dict]:
    """Parse workout rows from a CSV file."""
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [row for row in reader]
    if not rows:
        raise ValueError(f"No workout rows found in '{filepath}'.")
    return rows


def parse_json(filepath: str) -> list[dict]:
    """Parse workout entries from a JSON file (list of objects)."""
    with open(filepath, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON array of workout objects in '{filepath}'."
        )
    if not data:
        raise ValueError(f"No workout entries found in '{filepath}'.")
    return data


# ---------------------------------------------------------------------------
# ICS creation
# ---------------------------------------------------------------------------

def _build_description(workout: dict) -> str:
    """Build a human-readable description from optional workout fields."""
    parts: list[str] = []

    distance = _parse_float(workout.get("distance_km"))
    if distance is not None:
        parts.append(f"Distance: {distance:g} km")

    elevation = _parse_float(workout.get("elevation_m"))
    if elevation is not None:
        parts.append(f"Elevation gain: {elevation:g} m")

    notes = str(workout.get("notes") or "").strip()
    if notes:
        parts.append(f"Notes: {notes}")

    return "\n".join(parts)


def workout_to_event(workout: dict) -> Event:
    """Convert a workout dictionary to an :class:`icalendar.Event`."""
    name = str(workout.get("name") or "").strip()
    if not name:
        raise ValueError(f"Workout is missing a 'name': {workout}")

    date_str = str(workout.get("date") or "").strip()
    if not date_str:
        raise ValueError(f"Workout '{name}' is missing a 'date'.")

    time_str = str(workout.get("time") or "").strip()
    dtstart = _parse_datetime(date_str, time_str)

    duration_raw = _parse_float(workout.get("duration_minutes"))
    if duration_raw is None:
        raise ValueError(
            f"Workout '{name}' is missing a valid 'duration_minutes'."
        )
    duration = timedelta(minutes=duration_raw)

    event = Event()
    event.add("summary", name)
    event.add("dtstart", dtstart)
    event.add("duration", duration)

    description = _build_description(workout)
    if description:
        event.add("description", description)

    event.add("uid", str(uuid.uuid4()))
    return event


def create_calendar(workouts: list[dict]) -> Calendar:
    """Return an :class:`icalendar.Calendar` populated with *workouts*."""
    cal = Calendar()
    cal.add("prodid", "-//CampusToCalendar//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Campus Coach Workouts")

    errors: list[str] = []
    added = 0
    for i, workout in enumerate(workouts, start=1):
        try:
            event = workout_to_event(workout)
            cal.add_component(event)
            added += 1
        except ValueError as exc:
            errors.append(f"  Row {i}: {exc}")

    if errors:
        print("Warning – skipped workouts with invalid data:", file=sys.stderr)
        for msg in errors:
            print(msg, file=sys.stderr)

    if added == 0:
        raise ValueError("No valid workout entries could be converted.")

    return cal


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _detect_format(path: str) -> str:
    return "json" if path.lower().endswith(".json") else "csv"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert Campus Coach planned workouts to ICS calendar format.\n\n"
            "The output .ics file can be imported into Google Calendar, "
            "Apple Calendar, or any other iCalendar-compatible app."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        help="Path to the input file (CSV or JSON).",
    )
    parser.add_argument(
        "-o", "--output",
        default="workouts.ics",
        help="Path for the output ICS file (default: workouts.ics).",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["csv", "json"],
        help=(
            "Input format. Auto-detected from the file extension when "
            "not specified."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    fmt = args.format or _detect_format(args.input)

    try:
        workouts = parse_json(args.input) if fmt == "json" else parse_csv(args.input)
        cal = create_calendar(workouts)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    ics_bytes = cal.to_ical()
    try:
        with open(args.output, "wb") as fh:
            fh.write(ics_bytes)
    except OSError as exc:
        print(f"Error writing '{args.output}': {exc}", file=sys.stderr)
        return 1

    event_count = sum(
        1 for comp in cal.walk() if comp.name == "VEVENT"
    )
    print(
        f"Created '{args.output}' with {event_count} workout event(s). "
        "Import this file into Google Calendar or Apple Calendar."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
