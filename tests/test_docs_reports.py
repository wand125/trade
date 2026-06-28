import re
import unittest
from datetime import datetime
from pathlib import Path


REPORT_NAME_PATTERN = re.compile(r"^(?P<number>\d{5})_\d{4}-\d{2}-\d{2}_.+\.md$")
REPORT_TIME_PATTERN = re.compile(r"^日時: (?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) JST$", re.MULTILINE)
REPORT_UPDATED_PATTERN = re.compile(r"^更新日時: \d{4}-\d{2}-\d{2} \d{2}:\d{2} JST$", re.MULTILINE)


def read_internal_report_time(path: Path) -> datetime:
    text = path.read_text(encoding="utf-8")
    time_match = REPORT_TIME_PATTERN.search(text)
    if time_match is None:
        raise AssertionError(f"missing internal report time: {path.name}")
    if REPORT_UPDATED_PATTERN.search(text) is None:
        raise AssertionError(f"missing updated report time: {path.name}")
    return datetime.strptime(time_match.group("time"), "%Y-%m-%d %H:%M")


class DocsReportTests(unittest.TestCase):
    def test_report_numbers_follow_internal_report_time(self):
        report_paths = sorted(Path("docs/reports").glob("*.md"))
        self.assertGreater(len(report_paths), 0)

        rows = []
        for path in report_paths:
            name_match = REPORT_NAME_PATTERN.match(path.name)
            self.assertIsNotNone(name_match, path.name)
            rows.append(
                {
                    "path": path,
                    "number": int(name_match.group("number")),
                    "report_time": read_internal_report_time(path),
                }
            )

        self.assertEqual([row["number"] for row in rows], list(range(1, len(rows) + 1)))
        by_internal_time = sorted(rows, key=lambda row: (row["report_time"], row["path"].name))
        self.assertEqual(
            [row["path"].name for row in rows],
            [row["path"].name for row in by_internal_time],
        )


if __name__ == "__main__":
    unittest.main()
