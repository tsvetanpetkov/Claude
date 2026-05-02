#!/usr/bin/env python3
"""
Download earnings call transcripts from The Motley Fool (no API key required).
"""

import re
import sys
import time
import argparse
import xml.etree.ElementTree as ET
import requests
from pathlib import Path
from bs4 import BeautifulSoup

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

RSS_URL = "https://www.fool.com/feeds/index.aspx?id=earnings-call-transcripts"
SEARCH_URL = "https://www.fool.com/search/"
BASE_URL = "https://www.fool.com"


def find_transcript_urls(ticker: str, limit: int) -> list[dict]:
    """Return transcript metadata from the Motley Fool RSS feed, filtered by ticker."""
    resp = requests.get(RSS_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    matches = []
    ticker_pattern = re.compile(rf"\b{re.escape(ticker)}\b", re.IGNORECASE)

    for item in root.iter("item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub_date = item.findtext("pubDate") or ""

        if ticker_pattern.search(title):
            matches.append({"title": title.strip(), "url": link.strip(), "date": pub_date.strip()})
            if len(matches) >= limit:
                break

    # Fall back to site search if RSS didn't have enough results
    if len(matches) < limit:
        matches.extend(_search_transcripts(ticker, limit - len(matches), seen={m["url"] for m in matches}))

    return matches[:limit]


def _search_transcripts(ticker: str, limit: int, seen: set) -> list[dict]:
    params = {"q": f"{ticker} earnings call transcript", "resultsperpage": str(limit + 5)}
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "transcript" in href.lower() and ticker.lower() in href.lower():
            url = href if href.startswith("http") else BASE_URL + href
            if url not in seen:
                seen.add(url)
                results.append({"title": a.get_text(strip=True), "url": url, "date": ""})
                if len(results) >= limit:
                    break
    return results


def scrape_article(url: str) -> str | None:
    """Fetch a Motley Fool article and extract the body text."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try progressively broader content selectors
    container = None
    for selector in [
        {"class": re.compile(r"article-body", re.I)},
        {"class": re.compile(r"content", re.I)},
    ]:
        container = soup.find("div", selector)
        if container:
            break
    if not container:
        container = soup.find("article") or soup.find("main") or soup.find("body")

    if not container:
        return None

    paragraphs = container.find_all(["p", "h2", "h3"])
    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    return text if len(text) > 300 else None


def download_transcripts(
    tickers: list[str],
    output_dir: str,
    limit: int = 4,
    delay: float = 1.5,
) -> int:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    total_saved = 0

    for ticker in tickers:
        print(f"\n{ticker}: searching Motley Fool for transcripts...")
        ticker_dir = output_path / ticker
        ticker_dir.mkdir(exist_ok=True)

        try:
            entries = find_transcript_urls(ticker, limit)
        except Exception as e:
            print(f"  Error fetching transcript list: {e}")
            continue

        if not entries:
            print(f"  No transcripts found for {ticker}.")
            continue

        print(f"  Found {len(entries)} candidate(s).")
        saved = 0

        for i, entry in enumerate(entries):
            url = entry["url"]
            title = entry["title"] or f"transcript_{i+1}"
            date = entry["date"]

            try:
                content = scrape_article(url)
            except requests.RequestException as e:
                print(f"  Skipped ({e}): {url}")
                time.sleep(delay)
                continue

            if not content:
                print(f"  Skipped (no content): {url}")
                time.sleep(delay)
                continue

            filename = ticker_dir / f"{ticker}_transcript_{i+1:02d}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Ticker:  {ticker}\n")
                f.write(f"Title:   {title}\n")
                f.write(f"Date:    {date}\n")
                f.write(f"Source:  {url}\n")
                f.write("=" * 72 + "\n\n")
                f.write(content)
                f.write("\n")

            print(f"  Saved → {filename}")
            saved += 1
            total_saved += 1
            time.sleep(delay)

        print(f"  {saved} transcript(s) saved for {ticker}.")

    return total_saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download earnings call transcripts from The Motley Fool.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        default=DEFAULT_TICKERS,
        metavar="TICKER",
        help="Ticker symbols (e.g. AAPL MSFT TSLA)",
    )
    parser.add_argument("--output-dir", default="transcripts", help="Output directory")
    parser.add_argument("--limit", type=int, default=4, metavar="N", help="Max transcripts per company")
    parser.add_argument("--delay", type=float, default=1.5, metavar="SECONDS", help="Delay between requests")

    args = parser.parse_args()
    tickers = [t.upper().strip() for t in args.tickers if t.strip()]
    if not tickers:
        print("Error: no tickers specified.")
        sys.exit(1)

    print(f"Downloading transcripts for: {', '.join(tickers)}")
    print(f"Source: The Motley Fool (no API key required)\n")

    saved = download_transcripts(tickers, args.output_dir, args.limit, args.delay)
    print(f"\nDone. {saved} transcript(s) saved under ./{args.output_dir}/")

    if saved == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
