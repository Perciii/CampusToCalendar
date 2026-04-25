"""Tests for campus_to_calendar.py"""

import io
import os
import sys
import tempfile
import textwrap
import unittest
from datetime import timedelta, timezone
from unittest.mock import patch

# Ensure the project root is on the path when running tests directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from campus_to_calendar import (
    _build_description,
    _parse_datetime,
    _parse_float,
    create_calendar,
    main,
    parse_csv,
    parse_json,
    workout_to_event,
)


# ---------------------------------------------------------------------------
# _parse_float
# ---------------------------------------------------------------------------

class TestParseFloat(unittest.TestCase):
    def test_valid_integer_string(self):
        self.assertEqual(_parse_float("42"), 42.0)

    def test_valid_float_string(self):
        self.assertAlmostEqual(_parse_float("3.14"), 3.14)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_float(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_float(""))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(_parse_float("abc"))

    def test_whitespace_stripped(self):
        self.assertEqual(_parse_float("  10  "), 10.0)


# ---------------------------------------------------------------------------
# _parse_datetime
# ---------------------------------------------------------------------------

class TestParseDatetime(unittest.TestCase):
    def test_valid_date_and_time(self):
        dt = _parse_datetime("2024-06-01", "07:30")
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 6)
        self.assertEqual(dt.day, 1)
        self.assertEqual(dt.hour, 7)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_missing_time_defaults_to_0900(self):
        dt = _parse_datetime("2024-06-01", "")
        self.assertEqual(dt.hour, 9)
        self.assertEqual(dt.minute, 0)

    def test_none_time_defaults_to_0900(self):
        dt = _parse_datetime("2024-06-01", None)
        self.assertEqual(dt.hour, 9)
        self.assertEqual(dt.minute, 0)

    def test_invalid_date_raises(self):
        with self.assertRaises(ValueError):
            _parse_datetime("not-a-date", "09:00")


# ---------------------------------------------------------------------------
# _build_description
# ---------------------------------------------------------------------------

class TestBuildDescription(unittest.TestCase):
    def test_all_optional_fields(self):
        w = {"distance_km": 10.5, "elevation_m": 200, "notes": "Hard effort"}
        desc = _build_description(w)
        self.assertIn("10.5 km", desc)
        self.assertIn("200 m", desc)
        self.assertIn("Hard effort", desc)

    def test_no_optional_fields(self):
        self.assertEqual(_build_description({}), "")

    def test_only_distance(self):
        desc = _build_description({"distance_km": 5.0})
        self.assertIn("5 km", desc)
        self.assertNotIn("Elevation", desc)

    def test_only_elevation(self):
        desc = _build_description({"elevation_m": 300})
        self.assertIn("300 m", desc)
        self.assertNotIn("Distance", desc)

    def test_missing_notes_omitted(self):
        desc = _build_description({"distance_km": 8.0, "notes": ""})
        self.assertNotIn("Notes", desc)


# ---------------------------------------------------------------------------
# workout_to_event
# ---------------------------------------------------------------------------

class TestWorkoutToEvent(unittest.TestCase):
    def _minimal(self, **kwargs):
        base = {
            "name": "Easy Run",
            "date": "2024-06-01",
            "duration_minutes": 45,
        }
        base.update(kwargs)
        return base

    def test_basic_event_fields(self):
        event = workout_to_event(self._minimal())
        self.assertEqual(str(event["summary"]), "Easy Run")
        self.assertEqual(event["duration"].dt, timedelta(minutes=45))

    def test_description_includes_distance(self):
        event = workout_to_event(self._minimal(distance_km=10.0))
        self.assertIn("10", str(event["description"]))

    def test_description_includes_elevation(self):
        event = workout_to_event(self._minimal(elevation_m=250))
        self.assertIn("250", str(event["description"]))

    def test_uid_is_unique(self):
        e1 = workout_to_event(self._minimal())
        e2 = workout_to_event(self._minimal())
        self.assertNotEqual(str(e1["uid"]), str(e2["uid"]))

    def test_missing_name_raises(self):
        with self.assertRaises(ValueError):
            workout_to_event({"date": "2024-06-01", "duration_minutes": 30})

    def test_missing_date_raises(self):
        with self.assertRaises(ValueError):
            workout_to_event({"name": "Run", "duration_minutes": 30})

    def test_missing_duration_raises(self):
        with self.assertRaises(ValueError):
            workout_to_event({"name": "Run", "date": "2024-06-01"})

    def test_custom_start_time(self):
        event = workout_to_event(self._minimal(time="06:45"))
        self.assertEqual(event["dtstart"].dt.hour, 6)
        self.assertEqual(event["dtstart"].dt.minute, 45)


# ---------------------------------------------------------------------------
# parse_csv / parse_json
# ---------------------------------------------------------------------------

class TestParsers(unittest.TestCase):
    def _write_tmp(self, content: str, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def test_parse_csv_basic(self):
        csv_content = textwrap.dedent("""\
            name,date,duration_minutes,distance_km
            Easy Run,2024-06-01,45,8.0
            Tempo Run,2024-06-03,50,9.0
        """)
        path = self._write_tmp(csv_content, ".csv")
        try:
            rows = parse_csv(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["name"], "Easy Run")
        finally:
            os.unlink(path)

    def test_parse_csv_empty_raises(self):
        path = self._write_tmp("name,date,duration_minutes\n", ".csv")
        try:
            with self.assertRaises(ValueError):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_parse_json_basic(self):
        json_content = '[{"name":"Run","date":"2024-06-01","duration_minutes":30}]'
        path = self._write_tmp(json_content, ".json")
        try:
            rows = parse_json(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Run")
        finally:
            os.unlink(path)

    def test_parse_json_not_list_raises(self):
        path = self._write_tmp('{"name":"Run"}', ".json")
        try:
            with self.assertRaises(ValueError):
                parse_json(path)
        finally:
            os.unlink(path)

    def test_parse_json_empty_list_raises(self):
        path = self._write_tmp("[]", ".json")
        try:
            with self.assertRaises(ValueError):
                parse_json(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# create_calendar
# ---------------------------------------------------------------------------

class TestCreateCalendar(unittest.TestCase):
    def _valid_workouts(self):
        return [
            {
                "name": "Easy Run",
                "date": "2024-06-01",
                "duration_minutes": 45,
                "distance_km": 8.0,
                "elevation_m": 50,
            },
            {
                "name": "Long Run",
                "date": "2024-06-08",
                "duration_minutes": 90,
                "distance_km": 16.0,
            },
        ]

    def test_event_count(self):
        cal = create_calendar(self._valid_workouts())
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(events), 2)

    def test_calendar_name(self):
        cal = create_calendar(self._valid_workouts())
        self.assertIn(b"Campus Coach", cal.to_ical())

    def test_invalid_rows_skipped_with_warning(self):
        workouts = self._valid_workouts()
        workouts.append({"name": "Bad", "date": "2024-06-10"})  # missing duration
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            cal = create_calendar(workouts)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(events), 2)  # bad row skipped
        self.assertIn("Row 3", stderr_capture.getvalue())

    def test_all_invalid_rows_raises(self):
        with self.assertRaises(ValueError):
            create_calendar([{"name": "Bad"}])  # no date or duration

    def test_ical_output_is_bytes(self):
        cal = create_calendar(self._valid_workouts())
        self.assertIsInstance(cal.to_ical(), bytes)


# ---------------------------------------------------------------------------
# main() / CLI integration
# ---------------------------------------------------------------------------

class TestMainCLI(unittest.TestCase):
    def _csv_file(self):
        content = textwrap.dedent("""\
            name,date,time,duration_minutes,distance_km,elevation_m,notes
            Easy Run,2024-06-03,07:30,45,8.0,50,Keep it easy
            Tempo Run,2024-06-05,07:00,50,9.0,40,At threshold
        """)
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def _json_file(self):
        import json as _json
        data = [
            {"name": "Easy Run", "date": "2024-06-03", "duration_minutes": 45,
             "distance_km": 8.0, "elevation_m": 50},
        ]
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            _json.dump(data, fh)
        return path

    def test_csv_creates_ics(self):
        csv_path = self._csv_file()
        fd, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            rc = main([csv_path, "-o", out_path])
            self.assertEqual(rc, 0)
            with open(out_path, "rb") as fh:
                content = fh.read()
            self.assertIn(b"BEGIN:VCALENDAR", content)
            self.assertIn(b"Easy Run", content)
            self.assertIn(b"Tempo Run", content)
        finally:
            os.unlink(csv_path)
            os.unlink(out_path)

    def test_json_creates_ics(self):
        json_path = self._json_file()
        fd, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            rc = main([json_path, "-o", out_path])
            self.assertEqual(rc, 0)
            with open(out_path, "rb") as fh:
                content = fh.read()
            self.assertIn(b"BEGIN:VCALENDAR", content)
        finally:
            os.unlink(json_path)
            os.unlink(out_path)

    def test_missing_input_file_returns_error(self):
        rc = main(["nonexistent_file.csv", "-o", "/tmp/out.ics"])
        self.assertEqual(rc, 1)

    def test_format_flag_overrides_extension(self):
        """A .txt file treated as CSV when --format csv is given."""
        content = "name,date,duration_minutes\nRun,2024-06-01,30\n"
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
        fd2, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd2)
        try:
            rc = main([path, "-f", "csv", "-o", out_path])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(path)
            os.unlink(out_path)

    def test_sample_csv_file(self):
        """Run against the bundled sample CSV data."""
        sample = os.path.join(
            os.path.dirname(__file__), "..", "sample_data", "workouts.csv"
        )
        fd, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            rc = main([sample, "-o", out_path])
            self.assertEqual(rc, 0)
            with open(out_path, "rb") as fh:
                content = fh.read()
            self.assertIn(b"Easy Run", content)
            self.assertIn(b"Long Run", content)
        finally:
            os.unlink(out_path)

    def test_sample_json_file(self):
        """Run against the bundled sample JSON data."""
        sample = os.path.join(
            os.path.dirname(__file__), "..", "sample_data", "workouts.json"
        )
        fd, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            rc = main([sample, "-o", out_path])
            self.assertEqual(rc, 0)
            with open(out_path, "rb") as fh:
                content = fh.read()
            self.assertIn(b"Easy Run", content)
        finally:
            os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
