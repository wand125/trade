from __future__ import annotations

import argparse
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests


BASE_URL = "https://www.histdata.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


MODE_SLUGS = {
    "m1": "1-minute-bar-quotes",
    "tick": "tick-data-quotes",
}

MODE_TIMEFRAMES = {
    "m1": "M1",
    "tick": "T",
}


@dataclass(frozen=True)
class Period:
    mode: str
    pair: str
    year: int
    month: int | None
    url: str

    @property
    def key(self) -> str:
        if self.month is None:
            return f"{self.year}"
        return f"{self.year}{self.month:02d}"

    @property
    def filename(self) -> str:
        timeframe = MODE_TIMEFRAMES[self.mode]
        return f"HISTDATA_COM_ASCII_{self.pair.upper()}_{timeframe}_{self.key}.zip"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


class DownloadFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_file_down = False
        self.depth = 0
        self.inputs: dict[str, str] = {}
        self.file_link = ""
        self._capture_file_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()
        if tag == "form" and attrs_dict.get("id") == "file_down":
            self.in_file_down = True
            self.depth = 1
            return
        if self.in_file_down:
            if tag == "form":
                self.depth += 1
            if tag == "input":
                name = attrs_dict.get("name")
                value = attrs_dict.get("value")
                if name and value is not None:
                    self.inputs[name] = value
            return
        if tag == "a" and attrs_dict.get("id") == "a_file":
            self._capture_file_link = True

    def handle_endtag(self, tag: str) -> None:
        if self.in_file_down and tag.lower() == "form":
            self.depth -= 1
            if self.depth <= 0:
                self.in_file_down = False
        if tag.lower() == "a":
            self._capture_file_link = False

    def handle_data(self, data: str) -> None:
        if self._capture_file_link:
            self.file_link += data.strip()


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_text(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.text


def pair_page_url(pair: str, mode: str) -> str:
    slug = MODE_SLUGS[mode]
    return f"{BASE_URL}/download-free-forex-historical-data/?/ascii/{slug}/{pair.lower()}"


def parse_period_links(html: str, pair: str, mode: str) -> list[Period]:
    parser = LinkParser()
    parser.feed(html)
    slug = MODE_SLUGS[mode]
    pair = pair.lower()
    pattern = re.compile(
        rf"/download-free-forex-historical-data/\?/ascii/{slug}/{pair}/"
        rf"(?P<year>\d{{4}})(?:/(?P<month>\d{{1,2}}))?$",
        re.IGNORECASE,
    )
    periods: dict[tuple[int, int | None], Period] = {}
    for href in parser.links:
        match = pattern.search(href)
        if not match:
            continue
        year = int(match.group("year"))
        month_value = match.group("month")
        month = int(month_value) if month_value else None
        if month is not None and not 1 <= month <= 12:
            continue
        url = urljoin(BASE_URL, href)
        periods[(year, month)] = Period(mode, pair.upper(), year, month, url)
    return sorted(periods.values(), key=lambda item: (item.year, item.month or 0))


def collect_m1_periods(
    session: requests.Session,
    pair: str,
    start_year: int,
    end_year: int,
    start_month: int,
    end_month: int,
) -> list[Period]:
    html = fetch_text(session, pair_page_url(pair, "m1"))
    periods = parse_period_links(html, pair, "m1")
    return [
        period
        for period in periods
        if period_in_range(period, start_year, end_year, start_month, end_month)
    ]


def collect_tick_periods(
    session: requests.Session,
    pair: str,
    start_year: int,
    end_year: int,
    start_month: int,
    end_month: int,
) -> list[Period]:
    html = fetch_text(session, pair_page_url(pair, "tick"))
    year_periods = parse_period_links(html, pair, "tick")
    months: list[Period] = []
    for year_period in year_periods:
        if not start_year <= year_period.year <= end_year:
            continue
        year_html = fetch_text(session, year_period.url)
        for month_period in parse_period_links(year_html, pair, "tick"):
            if period_in_range(month_period, start_year, end_year, start_month, end_month):
                months.append(month_period)
    return sorted(months, key=lambda item: (item.year, item.month or 0))


def period_in_range(
    period: Period,
    start_year: int,
    end_year: int,
    start_month: int,
    end_month: int,
) -> bool:
    if period.year < start_year or period.year > end_year:
        return False
    if period.month is None:
        return True
    start_key = start_year * 100 + start_month
    end_key = end_year * 100 + end_month
    period_key = period.year * 100 + period.month
    return start_key <= period_key <= end_key


def parse_download_form(html: str) -> tuple[dict[str, str], str]:
    parser = DownloadFormParser()
    parser.feed(html)
    required = {"tk", "date", "datemonth", "platform", "timeframe", "fxpair"}
    missing = sorted(required - set(parser.inputs))
    if missing:
        raise ValueError(f"download form is missing fields: {', '.join(missing)}")
    return parser.inputs, parser.file_link


def target_directory(root: Path, pair: str, mode: str) -> Path:
    return root / "histdata" / pair.lower() / mode


def validate_zip(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0 and zipfile.is_zipfile(path)


def download_period(
    session: requests.Session,
    period: Period,
    output_dir: Path,
    force: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / period.filename
    if validate_zip(output_path) and not force:
        print(f"skip existing valid zip: {output_path}")
        return output_path

    html = fetch_text(session, period.url)
    form_data, link_name = parse_download_form(html)
    if link_name and not link_name.endswith(".zip"):
        print(f"warning: unexpected download label for {period.url}: {link_name}")

    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    headers = {"Referer": period.url, "User-Agent": USER_AGENT}
    with session.post(
        f"{BASE_URL}/get.php",
        data=form_data,
        headers=headers,
        stream=True,
        timeout=(30, 300),
    ) as response:
        response.raise_for_status()
        with temp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    if not validate_zip(temp_path):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file is not a valid zip: {period.url}")

    temp_path.replace(output_path)
    print(f"downloaded: {output_path}")
    return output_path


def collect_periods(
    session: requests.Session,
    mode: str,
    pair: str,
    start_year: int,
    end_year: int,
    start_month: int,
    end_month: int,
) -> list[Period]:
    if mode == "m1":
        return collect_m1_periods(session, pair, start_year, end_year, start_month, end_month)
    if mode == "tick":
        return collect_tick_periods(session, pair, start_year, end_year, start_month, end_month)
    raise ValueError(f"unsupported mode: {mode}")


def add_download_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=sorted(MODE_SLUGS), required=True)
    parser.add_argument("--pair", default="XAUUSD")
    parser.add_argument("--start-year", type=int, default=2009)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--end-month", type=int, default=12)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def handle_download(args: argparse.Namespace) -> int:
    current_year = time.gmtime().tm_year
    end_year = args.end_year or current_year
    if args.start_year > end_year:
        raise SystemExit("--start-year must be <= --end-year")
    if not 1 <= args.start_month <= 12 or not 1 <= args.end_month <= 12:
        raise SystemExit("--start-month and --end-month must be between 1 and 12")

    session = make_session()
    periods = collect_periods(
        session=session,
        mode=args.mode,
        pair=args.pair,
        start_year=args.start_year,
        end_year=end_year,
        start_month=args.start_month,
        end_month=args.end_month,
    )
    if args.max_files is not None:
        periods = periods[: args.max_files]

    if not periods:
        print("no matching periods found")
        return 1

    print(f"found {len(periods)} {args.mode} period(s)")
    for period in periods:
        print(f"{period.key}: {period.url}")

    if args.dry_run:
        return 0

    output_dir = target_directory(args.raw_root, args.pair, args.mode)
    for index, period in enumerate(periods, start=1):
        print(f"[{index}/{len(periods)}] {period.filename}")
        download_period(session, period, output_dir, force=args.force)
        if args.sleep and index < len(periods):
            time.sleep(args.sleep)
    return 0


def handle_list(args: argparse.Namespace) -> int:
    session = make_session()
    periods = collect_periods(
        session=session,
        mode=args.mode,
        pair=args.pair,
        start_year=args.start_year,
        end_year=args.end_year or datetime.now(UTC).year,
        start_month=args.start_month,
        end_month=args.end_month,
    )
    for period in periods:
        print(f"{period.key}\t{period.url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download HistData XAUUSD data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="download ZIP files")
    add_download_args(download_parser)
    download_parser.set_defaults(func=handle_download)

    list_parser = subparsers.add_parser("list", help="list available periods")
    add_download_args(list_parser)
    list_parser.set_defaults(func=handle_list)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
