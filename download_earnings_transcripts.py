#!/usr/bin/env python3
"""
Download earnings call transcripts for public companies.

Uses the Financial Modeling Prep (FMP) API. A free API key is available at:
https://financialmodelingprep.com/developer/docs/

Set your key via the FMP_API_KEY environment variable or --api-key argument.
"""

import os
import sys
import time
import argparse
import requests
from pathlib import Path

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


def _get(url: str, params: dict) -> list[dict]:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    # FMP returns a dict with "Error Message" when the endpoint requires a paid plan
    if isinstance(data, dict):
        msg = data.get("Error Message") or data.get("message") or repr(data)
        raise RuntimeError(f"FMP API error: {msg}")
    return data


def list_available_transcripts(ticker: str, api_key: str) -> list[dict]:
    url = f"{FMP_BASE_URL}/earning_call_transcript/{ticker}"
    return _get(url, {"apikey": api_key})


def fetch_transcript(ticker: str, year: int, quarter: int, api_key: str) -> list[dict]:
    url = f"{FMP_BASE_URL}/earning_call_transcript/{ticker}"
    return _get(url, {"year": year, "quarter": quarter, "apikey": api_key})


def save_transcript(ticker_dir: Path, ticker: str, entry: dict) -> str | None:
    year = entry.get("year")
    quarter = entry.get("quarter")
    date = entry.get("date", "unknown date")
    content = entry.get("content", "").strip()

    if not content:
        return None

    filename = ticker_dir / f"{ticker}_Q{quarter}_{year}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Ticker:  {ticker}\n")
        f.write(f"Period:  Q{quarter} {year}\n")
        f.write(f"Date:    {date}\n")
        f.write("=" * 72 + "\n\n")
        f.write(content)
        f.write("\n")

    return str(filename)


def download_transcripts(
    tickers: list[str],
    output_dir: str,
    api_key: str,
    limit: int = 4,
    delay: float = 0.5,
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for ticker in tickers:
        print(f"\n{ticker}: fetching available transcripts...")
        ticker_dir = output_path / ticker
        ticker_dir.mkdir(exist_ok=True)

        try:
            available = list_available_transcripts(ticker, api_key)
        except (requests.HTTPError, RuntimeError) as e:
            print(f"  Error: {e}")
            continue

        if not available:
            print(f"  No transcripts found.")
            continue

        saved = 0
        for entry in available[:limit]:
            year = entry.get("year")
            quarter = entry.get("quarter")

            # The list endpoint may already include content; if not, fetch individually.
            content = entry.get("content", "")
            if not content:
                try:
                    results = fetch_transcript(ticker, year, quarter, api_key)
                    entry = results[0] if results else entry
                except (requests.HTTPError, RuntimeError, IndexError):
                    pass
                time.sleep(delay)

            path = save_transcript(ticker_dir, ticker, entry)
            if path:
                print(f"  Saved Q{quarter} {year} → {path}")
                saved += 1
            else:
                print(f"  Skipped Q{quarter} {year} (empty content)")

            time.sleep(delay)

        print(f"  {saved} transcript(s) saved for {ticker}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download earnings call transcripts for public companies.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        default=DEFAULT_TICKERS,
        metavar="TICKER",
        help="One or more ticker symbols (e.g. AAPL MSFT TSLA)",
    )
    parser.add_argument(
        "--output-dir",
        default="transcripts",
        help="Directory where transcripts will be saved",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("FMP_API_KEY"),
        help="Financial Modeling Prep API key (or set FMP_API_KEY env var)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=4,
        metavar="N",
        help="Maximum number of transcripts to download per company",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        metavar="SECONDS",
        help="Seconds to wait between API requests",
    )

    args = parser.parse_args()

    if not args.api_key:
        print("Error: an FMP API key is required.")
        print("  Get a free key at: https://financialmodelingprep.com/developer/docs/")
        print("  Then run:  export FMP_API_KEY=your_key_here")
        print("  Or pass:   --api-key your_key_here")
        sys.exit(1)

    tickers = [t.upper().strip() for t in args.tickers if t.strip()]
    if not tickers:
        print("Error: no tickers specified.")
        sys.exit(1)

    print(f"Downloading transcripts for: {', '.join(tickers)}")
    print(f"Output directory: {args.output_dir}/")
    print(f"Limit per company: {args.limit} quarters\n")

    download_transcripts(
        tickers=tickers,
        output_dir=args.output_dir,
        api_key=args.api_key,
        limit=args.limit,
        delay=args.delay,
    )

    print(f"\nDone. Transcripts saved under ./{args.output_dir}/")


if __name__ == "__main__":
    main()
