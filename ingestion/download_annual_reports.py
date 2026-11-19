from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import requests

# Expected structure:
#
# financial-analysis/
# ├── data/
# ├── ingestion/
# │   └── download_annual_reports.py
# ├── pyproject.toml
# └── uv.lock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

YEARS = (2023, 2024)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True)
class Report:
    company: str
    ticker: str
    year: int
    filename: str
    url: str
    validate_year: bool = True


class DownloadError(RuntimeError):
    """Raised when a report cannot be downloaded or validated."""


REPORTS = [
    # ==============================================================
    # HDFC Bank Limited (HDFCBANK)
    # ==============================================================
    Report(
        company="HDFC Bank Limited",
        ticker="HDFCBANK",
        year=2023,
        filename="HDFCBANK_2023_Annual_Report.pdf",
        url=(
            "https://www.hdfcbank.com/content/bbp/repositories/72379700-14e9-492b-9e13-6388114a09e0/"
            "hdfc-bank-annual-report-2022-23.pdf"
        ),
        validate_year=True,
    ),
    Report(
        company="HDFC Bank Limited",
        ticker="HDFCBANK",
        year=2024,
        filename="HDFCBANK_2024_Annual_Report.pdf",
        url=(
            "https://www.hdfcbank.com/content/bbp/repositories/72379700-14e9-492b-9e13-6388114a09e0/"
            "hdfc-bank-annual-report-2023-24.pdf"
        ),
        validate_year=True,
    ),
    # ==============================================================
    # One97 Communications Limited (Paytm) (PAYTM)
    # ==============================================================
    Report(
        company="One97 Communications Limited (Paytm)",
        ticker="PAYTM",
        year=2023,
        filename="PAYTM_2023_Annual_Report.pdf",
        url=(
            "https://ir.paytm.com/pdf/annual-reports/Annual-Report-2022-23.pdf"
        ),
        validate_year=True,
    ),
    Report(
        company="One97 Communications Limited (Paytm)",
        ticker="PAYTM",
        year=2024,
        filename="PAYTM_2024_Annual_Report.pdf",
        url=(
            "https://ir.paytm.com/pdf/annual-reports/Annual-Report-2023-24.pdf"
        ),
        validate_year=True,
    ),
    # ==============================================================
    # ICICI Bank Limited (ICICIBANK)
    # ==============================================================
    Report(
        company="ICICI Bank Limited",
        ticker="ICICIBANK",
        year=2023,
        filename="ICICIBANK_2023_Annual_Report.pdf",
        url=(
            "https://www.icicibank.com/managed-assets/docs/investor/annual-reports/2023/annual-report-2022-23.pdf"
        ),
        validate_year=True,
    ),
    Report(
        company="ICICI Bank Limited",
        ticker="ICICIBANK",
        year=2024,
        filename="ICICIBANK_2024_Annual_Report.pdf",
        url=(
            "https://www.icicibank.com/managed-assets/docs/investor/annual-reports/2024/annual-report-2023-24.pdf"
        ),
        validate_year=True,
    ),
]


def normalize_text(value: str) -> str:
    """Convert text to lowercase and collapse repeated whitespace."""

    return re.sub(r"\s+", " ", value).strip().lower()


def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 checksum of a downloaded file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def validate_pdf_bytes(content: bytes, url: str) -> None:
    """
    Confirm that the downloaded content is a PDF.

    This prevents an HTML error page or anti-bot page from being
    stored with a .pdf extension.
    """

    if not content:
        raise DownloadError(f"Empty response received from {url}")

    if not content.lstrip().startswith(b"%PDF"):
        preview = content[:150]

        raise DownloadError(
            f"The response from {url} is not a PDF. " f"First bytes: {preview!r}"
        )


def extract_report_year(path: Path) -> int | None:
    """
    Try to infer the financial year from the opening pages.

    Returns None when no year can be identified confidently.
    """

    try:
        with pymupdf.open(path) as document:
            pages_to_read = min(
                15,
                document.page_count,
            )

            text = " ".join(
                document[index].get_text("text") for index in range(pages_to_read)
            )

    except Exception as exc:
        raise DownloadError(f"Could not inspect {path.name}: {exc}") from exc

    normalized = normalize_text(text)

    patterns = (
        r"annual report(?: and accounts)?\s+(20\d{2})",
        r"annual report\s+for\s+(20\d{2})",
        r"integrated annual report\s+(20\d{2})",
        r"integrated report\s+(20\d{2})",
        r"for the year ended[^0-9]{0,60}(20\d{2})",
        r"financial year[^0-9]{0,20}(20\d{2})",
        r"year ended[^0-9]{0,40}(20\d{2})",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

    # Fallback: compare how often each target year appears.
    counts = {
        year: len(
            re.findall(
                rf"\b{year}\b",
                normalized,
            )
        )
        for year in YEARS
    }

    best_year, best_count = max(
        counts.items(),
        key=lambda item: item[1],
    )

    if best_count >= 3:
        return best_year

    return None


def validate_report_year(
    path: Path,
    expected_year: int,
) -> None:
    """
    Confirm that the PDF appears to represent the requested year.

    If the year cannot be inferred, a warning is printed rather than
    rejecting the file.
    """

    detected_year = extract_report_year(path)

    if detected_year is None:
        print(
            f"Warning: could not infer report year from "
            f"{path.name}; keeping the PDF."
        )
        return

    if detected_year != expected_year:
        raise DownloadError(
            f"{path.name} appears to be the {detected_year} report, "
            f"not the requested {expected_year} report."
        )


def download_pdf(
    session: requests.Session,
    report: Report,
    *,
    retries: int = 3,
) -> Path:
    """Download and validate one annual report."""

    destination = DATA_DIR / report.ticker.lower() / str(report.year) / report.filename

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Verify an existing file before deciding to skip it.
    if destination.exists():
        try:
            with destination.open("rb") as file:
                validate_pdf_bytes(
                    file.read(1024),
                    report.url,
                )

            if report.validate_year:
                validate_report_year(
                    destination,
                    report.year,
                )

            print("Already downloaded and verified: " f"{destination}")

            return destination

        except DownloadError as exc:
            print(
                f"Existing file is invalid and will be replaced:\n"
                f"{destination}\n"
                f"Reason: {exc}"
            )

            destination.unlink(missing_ok=True)

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        temporary_path = destination.with_suffix(destination.suffix + ".part")

        temporary_path.unlink(missing_ok=True)

        try:
            print(
                f"Downloading {report.company} "
                f"{report.year} "
                f"(attempt {attempt}/{retries})..."
            )

            with session.get(
                report.url,
                headers=HEADERS,
                timeout=(20, 240),
                allow_redirects=True,
                stream=True,
            ) as response:
                response.raise_for_status()

                first_chunk = True

                with temporary_path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue

                        if first_chunk:
                            validate_pdf_bytes(
                                chunk,
                                response.url,
                            )
                            first_chunk = False

                        file.write(chunk)

                if first_chunk:
                    raise DownloadError(
                        f"No data was downloaded from " f"{response.url}"
                    )

            temporary_path.replace(destination)

            if report.validate_year:
                try:
                    validate_report_year(
                        destination,
                        report.year,
                    )
                except Exception:
                    destination.unlink(missing_ok=True)
                    raise

            checksum = sha256_file(destination)
            size_mb = destination.stat().st_size / 1_048_576

            print(
                f"Saved: {destination}\n"
                f"Size: {size_mb:.2f} MB\n"
                f"SHA-256: {checksum}"
            )

            return destination

        except (
            requests.RequestException,
            DownloadError,
            OSError,
        ) as exc:
            last_error = exc

            temporary_path.unlink(missing_ok=True)

            print(f"Download attempt failed: {exc}")

            if attempt < retries:
                wait_seconds = 2**attempt

                print(f"Retrying in {wait_seconds} seconds...")

                time.sleep(wait_seconds)

    raise DownloadError(
        f"Could not download {report.company} " f"{report.year}: {last_error}"
    )


def main() -> None:
    """Download all configured annual reports."""

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = requests.Session()

    successful: list[Path] = []
    failed: list[str] = []

    for report in REPORTS:
        try:
            downloaded_path = download_pdf(
                session,
                report,
            )

            successful.append(downloaded_path)

        except Exception as exc:
            failed.append(
                f"{report.company} " f"{report.year} " f"({report.filename}): {exc}"
            )

    print("\nDownload summary")
    print("=" * 80)

    for path in successful:
        print(f"OK: {path}")

    for failure in failed:
        print(f"FAILED: {failure}")

    print(f"\nSuccessful downloads: {len(successful)}")
    print(f"Failed downloads: {len(failed)}")

    if failed:
        raise SystemExit("\nSome downloads failed. " "Successful downloads were kept.")

    print("\nAll reports were downloaded into: " f"{DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
