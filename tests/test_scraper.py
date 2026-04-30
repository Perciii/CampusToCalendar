"""Tests for scraper.py – pure-Python logic only (no browser required)."""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper import (
    assign_slots,
    dates_for_workouts,
    extract_workouts_from_cards,
    main,
    monday_of_week,
    parse_duration_minutes,
)


# ---------------------------------------------------------------------------
# parse_duration_minutes
# ---------------------------------------------------------------------------

class TestParseDurationMinutes(unittest.TestCase):
    def test_plain_minutes(self):
        self.assertEqual(parse_duration_minutes("30 min"), 30)

    def test_plain_minutes_no_space(self):
        self.assertEqual(parse_duration_minutes("50min"), 50)

    def test_hours_and_minutes(self):
        self.assertEqual(parse_duration_minutes("1h30"), 90)

    def test_hours_and_minutes_with_spaces(self):
        self.assertEqual(parse_duration_minutes("1 h 30 min"), 90)

    def test_hours_only(self):
        self.assertEqual(parse_duration_minutes("2h"), 120)

    def test_heure_french(self):
        self.assertEqual(parse_duration_minutes("1 heure 30 min"), 90)

    def test_heures_plural(self):
        self.assertEqual(parse_duration_minutes("2 heures"), 120)

    def test_large_minutes(self):
        self.assertEqual(parse_duration_minutes("90 min"), 90)

    def test_duration_embedded_in_text(self):
        self.assertEqual(parse_duration_minutes("Duration: 45 min remaining"), 45)

    def test_none_on_no_match(self):
        self.assertIsNone(parse_duration_minutes("easy run"))

    def test_none_on_empty(self):
        self.assertIsNone(parse_duration_minutes(""))

    def test_none_on_whitespace(self):
        self.assertIsNone(parse_duration_minutes("   "))

    def test_minutes_case_insensitive(self):
        self.assertEqual(parse_duration_minutes("45 MIN"), 45)


# ---------------------------------------------------------------------------
# monday_of_week
# ---------------------------------------------------------------------------

class TestMondayOfWeek(unittest.TestCase):
    def test_monday_returns_same_day(self):
        monday = date(2024, 6, 3)  # a Monday
        self.assertEqual(monday_of_week(monday), monday)

    def test_wednesday_returns_monday(self):
        wednesday = date(2024, 6, 5)
        self.assertEqual(monday_of_week(wednesday), date(2024, 6, 3))

    def test_sunday_returns_monday(self):
        sunday = date(2024, 6, 9)
        self.assertEqual(monday_of_week(sunday), date(2024, 6, 3))

    def test_saturday_returns_monday(self):
        saturday = date(2024, 6, 8)
        self.assertEqual(monday_of_week(saturday), date(2024, 6, 3))


# ---------------------------------------------------------------------------
# dates_for_workouts
# ---------------------------------------------------------------------------

class TestDatesForWorkouts(unittest.TestCase):
    def test_single_workout(self):
        start = date(2024, 6, 3)
        self.assertEqual(dates_for_workouts(start, 1), [start])

    def test_seven_workouts(self):
        start = date(2024, 6, 3)
        result = dates_for_workouts(start, 7)
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0], date(2024, 6, 3))  # Monday
        self.assertEqual(result[6], date(2024, 6, 9))  # Sunday

    def test_more_than_seven_wraps(self):
        start = date(2024, 6, 3)
        result = dates_for_workouts(start, 8)
        self.assertEqual(result[7], date(2024, 6, 10))  # next Monday

    def test_zero_workouts(self):
        self.assertEqual(dates_for_workouts(date(2024, 6, 3), 0), [])


# ---------------------------------------------------------------------------
# assign_slots
# ---------------------------------------------------------------------------

class TestAssignSlots(unittest.TestCase):
    def _mon(self):
        return date(2024, 6, 3)  # Monday

    def test_zero_workouts(self):
        self.assertEqual(assign_slots(0, self._mon()), [])

    def test_one_workout_at_5pm(self):
        slots = assign_slots(1, self._mon())
        self.assertEqual(slots, [(date(2024, 6, 3), "17:00")])

    def test_seven_workouts_one_per_day_at_5pm(self):
        slots = assign_slots(7, self._mon())
        self.assertEqual(len(slots), 7)
        for i, (d, t) in enumerate(slots):
            self.assertEqual(d, date(2024, 6, 3) + timedelta(days=i))
            self.assertEqual(t, "17:00")

    def test_eight_workouts_first_day_double(self):
        # 8 workouts: Mon gets 2 (10:00 + 17:00), Tue–Sun each get 1 (17:00)
        slots = assign_slots(8, self._mon())
        self.assertEqual(len(slots), 8)
        self.assertEqual(slots[0], (date(2024, 6, 3), "10:00"))  # Mon #1
        self.assertEqual(slots[1], (date(2024, 6, 3), "17:00"))  # Mon #2
        for i in range(2, 8):
            d, t = slots[i]
            self.assertEqual(d, date(2024, 6, 3) + timedelta(days=i - 1))
            self.assertEqual(t, "17:00")

    def test_nine_workouts_two_days_doubled(self):
        slots = assign_slots(9, self._mon())
        self.assertEqual(len(slots), 9)
        # Mon: 10:00 and 17:00
        self.assertEqual(slots[0], (date(2024, 6, 3), "10:00"))
        self.assertEqual(slots[1], (date(2024, 6, 3), "17:00"))
        # Tue: 10:00 and 17:00
        self.assertEqual(slots[2], (date(2024, 6, 4), "10:00"))
        self.assertEqual(slots[3], (date(2024, 6, 4), "17:00"))
        # Wed onward: 17:00
        for i in range(4, 9):
            _, t = slots[i]
            self.assertEqual(t, "17:00")

    def test_fourteen_workouts_all_days_double(self):
        slots = assign_slots(14, self._mon())
        self.assertEqual(len(slots), 14)
        for day in range(7):
            first = slots[day * 2]
            second = slots[day * 2 + 1]
            expected_date = date(2024, 6, 3) + timedelta(days=day)
            self.assertEqual(first, (expected_date, "10:00"))
            self.assertEqual(second, (expected_date, "17:00"))

    def test_two_workouts_on_same_day_times(self):
        # count=2 → base=0, extra=2 → day0 gets 1, day1 gets 1 (no doubling)
        slots = assign_slots(2, self._mon())
        self.assertEqual(slots[0], (date(2024, 6, 3), "17:00"))
        self.assertEqual(slots[1], (date(2024, 6, 4), "17:00"))


# ---------------------------------------------------------------------------
# extract_workouts_from_cards
# ---------------------------------------------------------------------------

class TestExtractWorkoutsFromCards(unittest.TestCase):
    def _week(self):
        return date(2024, 6, 3)  # Monday

    def test_basic_extraction(self):
        cards = [
            {"title": "Strength & Conditioning", "duration_text": "30 min"},
            {"title": "Base Endurance", "duration_text": "50 min"},
        ]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Strength & Conditioning")
        self.assertEqual(result[0]["duration_minutes"], 30)
        self.assertEqual(result[0]["date"], "2024-06-03")
        self.assertEqual(result[1]["name"], "Base Endurance")
        self.assertEqual(result[1]["duration_minutes"], 50)
        self.assertEqual(result[1]["date"], "2024-06-04")

    def test_single_workout_gets_5pm(self):
        cards = [{"title": "Easy Run", "duration_text": "30 min"}]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(result[0]["time"], "17:00")

    def test_seven_workouts_all_at_5pm(self):
        cards = [{"title": f"W{i}", "duration_text": "30 min"} for i in range(7)]
        result = extract_workouts_from_cards(cards, self._week())
        for w in result:
            self.assertEqual(w["time"], "17:00")

    def test_eight_workouts_first_day_double(self):
        # 8 workouts: Mon gets two (10:00 + 17:00), Tue–Sun get one at 17:00
        cards = [{"title": f"W{i}", "duration_text": "30 min"} for i in range(8)]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0]["date"], "2024-06-03")  # Mon
        self.assertEqual(result[0]["time"], "10:00")
        self.assertEqual(result[1]["date"], "2024-06-03")  # Mon (2nd)
        self.assertEqual(result[1]["time"], "17:00")
        # Tue–Sun: one workout each at 17:00
        for i in range(2, 8):
            self.assertEqual(result[i]["time"], "17:00")
            expected_date = (date(2024, 6, 3) + timedelta(days=i - 1)).isoformat()
            self.assertEqual(result[i]["date"], expected_date)

    def test_nine_workouts_two_days_doubled(self):
        cards = [{"title": f"W{i}", "duration_text": "30 min"} for i in range(9)]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(len(result), 9)
        self.assertEqual(result[0]["date"], "2024-06-03")
        self.assertEqual(result[0]["time"], "10:00")
        self.assertEqual(result[1]["date"], "2024-06-03")
        self.assertEqual(result[1]["time"], "17:00")
        self.assertEqual(result[2]["date"], "2024-06-04")
        self.assertEqual(result[2]["time"], "10:00")
        self.assertEqual(result[3]["date"], "2024-06-04")
        self.assertEqual(result[3]["time"], "17:00")

    def test_cards_with_hours_and_minutes(self):
        cards = [{"title": "Long Run", "duration_text": "1h30"}]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(result[0]["duration_minutes"], 90)

    def test_cards_with_unparseable_duration_are_skipped(self):
        cards = [
            {"title": "Easy Run", "duration_text": "30 min"},
            {"title": "Bad Card", "duration_text": "unknown"},
            {"title": "Tempo", "duration_text": "45 min"},
        ]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(len(result), 2)
        names = [w["name"] for w in result]
        self.assertNotIn("Bad Card", names)

    def test_cards_with_no_title_are_skipped(self):
        cards = [
            {"title": "", "duration_text": "30 min"},
            {"title": "Interval Training", "duration_text": "60 min"},
        ]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Interval Training")

    def test_empty_cards_list(self):
        result = extract_workouts_from_cards([], self._week())
        self.assertEqual(result, [])

    def test_consecutive_dates_assigned_seven_workouts(self):
        cards = [
            {"title": f"Workout {i}", "duration_text": "30 min"}
            for i in range(1, 8)
        ]
        result = extract_workouts_from_cards(cards, self._week())
        for i, workout in enumerate(result):
            expected_date = (self._week() + timedelta(days=i)).isoformat()
            self.assertEqual(workout["date"], expected_date)

    def test_special_characters_in_title(self):
        cards = [{"title": "Strength & Conditioning", "duration_text": "30 min"}]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(result[0]["name"], "Strength & Conditioning")

    def test_duration_text_with_surrounding_text(self):
        cards = [{"title": "Run", "duration_text": "Duration: 45 min"}]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertEqual(result[0]["duration_minutes"], 45)

    def test_workouts_have_time_field(self):
        cards = [{"title": "Run", "duration_text": "30 min"}]
        result = extract_workouts_from_cards(cards, self._week())
        self.assertIn("time", result[0])


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------

class TestScraperCLI(unittest.TestCase):
    def _make_workouts(self):
        return [
            {"name": "Strength & Conditioning", "date": "2024-06-03",
             "duration_minutes": 30},
            {"name": "Base Endurance", "date": "2024-06-04",
             "duration_minutes": 50},
        ]

    def test_missing_email_returns_error(self):
        rc = main(["--password", "pw", "--week", "2024-06-03"])
        self.assertEqual(rc, 1)

    def test_missing_password_returns_error(self):
        rc = main(["--email", "e@x.com", "--week", "2024-06-03"])
        self.assertEqual(rc, 1)

    def test_invalid_week_returns_error(self):
        rc = main(["--email", "e@x.com", "--password", "pw", "--week", "not-a-date"])
        self.assertEqual(rc, 1)

    def test_dry_run_prints_json(self):
        workouts = self._make_workouts()
        import io, json
        stdout_capture = io.StringIO()
        with patch("scraper.scrape", return_value=workouts), \
             patch("sys.stdout", stdout_capture):
            rc = main([
                "--email", "e@x.com", "--password", "pw",
                "--week", "2024-06-03", "--dry-run",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(stdout_capture.getvalue())
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["name"], "Strength & Conditioning")

    def test_scrape_error_returns_1(self):
        with patch("scraper.scrape", side_effect=Exception("network error")):
            rc = main(["--email", "e@x.com", "--password", "pw",
                       "--week", "2024-06-03"])
        self.assertEqual(rc, 1)

    def test_no_workouts_returns_1(self):
        with patch("scraper.scrape", return_value=[]):
            rc = main(["--email", "e@x.com", "--password", "pw",
                       "--week", "2024-06-03"])
        self.assertEqual(rc, 1)

    def test_writes_ics_file(self):
        workouts = self._make_workouts()
        fd, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            with patch("scraper.scrape", return_value=workouts):
                rc = main([
                    "--email", "e@x.com", "--password", "pw",
                    "--week", "2024-06-03", "-o", out_path,
                ])
            self.assertEqual(rc, 0)
            with open(out_path, "rb") as fh:
                content = fh.read()
            self.assertIn(b"BEGIN:VCALENDAR", content)
            self.assertIn(b"Strength", content)
            self.assertIn(b"Base Endurance", content)
        finally:
            os.unlink(out_path)

    def test_email_from_env_var(self):
        workouts = self._make_workouts()
        fd, out_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            env = {**os.environ, "CAMPUS_EMAIL": "env@x.com",
                   "CAMPUS_PASSWORD": "envpw"}
            with patch("scraper.scrape", return_value=workouts), \
                 patch.dict("os.environ", env):
                rc = main(["--week", "2024-06-03", "-o", out_path])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
