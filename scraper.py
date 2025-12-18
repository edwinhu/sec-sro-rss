#!/usr/bin/env python3
"""
SEC SRO Rulemaking RSS Feed Generator

Scrapes SEC Self-Regulatory Organization rulemaking pages and generates
an RSS feed, filtering out:
- "Notice of Filing and Immediate Effectiveness" items
- Crypto/digital asset related listings
"""

import re
import time
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# Configuration
SEC_BASE_URL = "https://www.sec.gov"
SRO_PAGES = {
    "national-securities-exchanges": f"{SEC_BASE_URL}/rules-regulations/self-regulatory-organization-rulemaking/national-securities-exchanges",
    "finra": f"{SEC_BASE_URL}/rules-regulations/self-regulatory-organization-rulemaking/finra",
}

# Filtering patterns
EXCLUDE_TITLE_PATTERNS = [
    r"Notice of Filing and Immediate Effectiveness",
    r"Filing and Immediate Effectiveness",
]

CRYPTO_PATTERNS = [
    r"\bcrypto\b",
    r"\bcryptocurrency\b",
    r"\bcryptocurrencies\b",
    r"\bbitcoin\b",
    r"\bether\b",
    r"\bethereum\b",
    r"\bdigital\s+asset",
    r"\bblockchain\b",
    r"\bstablecoin\b",
    r"\btoken\b",
    r"\bBTC\b",
    r"\bETH\b",
    r"\bXRP\b",
    r"\bSOL\b",
    r"\bADA\b",
    r"\bDOGE\b",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 2  # seconds between requests to respect rate limits


class SROFiling(NamedTuple):
    """Represents a single SRO filing."""
    title: str
    url: str
    date: str
    description: str
    source: str  # 'finra' or 'national-securities-exchanges'

    @property
    def id(self) -> str:
        """Generate unique ID for this filing."""
        return hashlib.md5(self.url.encode()).hexdigest()[:12]


def should_exclude(title: str, description: str = "") -> bool:
    """Check if a filing should be excluded based on title/description."""
    text = f"{title} {description}".lower()

    # Check immediate effectiveness patterns
    for pattern in EXCLUDE_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    # Check crypto patterns
    for pattern in CRYPTO_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def fetch_page(url: str, session: requests.Session) -> str | None:
    """Fetch a page with proper headers and error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def parse_sro_page(html: str, source: str) -> list[SROFiling]:
    """Parse SRO rulemaking page and extract filings.

    The SEC page has a table with columns:
    - Release Number (with PDF link)
    - SEC Issue Date
    - File Number
    - SRO Organization
    - Details (description text)
    """
    soup = BeautifulSoup(html, "lxml")
    filings = []

    # Find the main data table
    for row in soup.select("table tbody tr"):
        try:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            # Column 0: Release Number with PDF link
            release_link = cells[0].select_one("a[href]")
            if not release_link:
                continue

            release_number = release_link.get_text(strip=True)
            # Clean up "External." prefix
            release_number = release_number.replace("External.", "").strip()

            pdf_href = release_link.get("href", "")
            if not pdf_href.startswith("http"):
                pdf_href = SEC_BASE_URL + pdf_href

            # Column 1: SEC Issue Date (e.g., "Dec 18, 2025")
            date_str = cells[1].get_text(strip=True)

            # Column 2: File Number (e.g., "SR-NASDAQ-2025-080")
            file_number = cells[2].get_text(strip=True)

            # Column 3: SRO Organization
            sro_org = cells[3].get_text(strip=True)

            # Column 4: Details - the main description text
            # Get only direct text, not nested link text
            details_cell = cells[4]
            # Get text before "Comments Due:" or "See Also"
            details_text = ""
            for child in details_cell.children:
                if hasattr(child, 'name'):
                    if child.name == 'strong':
                        break  # Stop at "Comments Due:"
                    if child.name == 'a' and 'Submit a Comment' in child.get_text():
                        continue  # Skip comment links
                else:
                    details_text += str(child)
            details_text = details_text.strip()

            # Build a descriptive title
            title = f"[{release_number}] {details_text[:200]}"
            if len(details_text) > 200:
                title += "..."

            # Store full details for filtering (will check against details_text)
            full_description = f"{sro_org} | {file_number} | {details_text}"

            filing = SROFiling(
                title=title,
                url=pdf_href,
                date=date_str,
                description=full_description,
                source=source,
            )
            filings.append(filing)

        except Exception as e:
            print(f"Error parsing row: {e}")
            continue

    return filings


def scrape_all_pages(max_pages: int = 3) -> list[SROFiling]:
    """Scrape all configured SRO pages."""
    all_filings = []
    session = requests.Session()

    for source, base_url in SRO_PAGES.items():
        print(f"Scraping {source}...")

        for page_num in range(max_pages):
            url = base_url if page_num == 0 else f"{base_url}?page={page_num}"
            print(f"  Fetching page {page_num + 1}: {url}")

            html = fetch_page(url, session)
            if not html:
                break

            # Check for rate limiting
            if "Request Rate Threshold Exceeded" in html:
                print("  Rate limited, waiting...")
                time.sleep(10)
                html = fetch_page(url, session)
                if not html or "Request Rate Threshold Exceeded" in html:
                    print("  Still rate limited, skipping...")
                    break

            filings = parse_sro_page(html, source)
            if not filings:
                print(f"  No filings found on page {page_num + 1}, stopping pagination")
                break

            all_filings.extend(filings)
            print(f"  Found {len(filings)} filings")

            time.sleep(REQUEST_DELAY)

    return all_filings


def filter_filings(filings: list[SROFiling]) -> list[SROFiling]:
    """Filter out excluded filings."""
    filtered = []
    excluded_count = 0

    for filing in filings:
        if should_exclude(filing.title, filing.description):
            excluded_count += 1
            print(f"  Excluding: {filing.title[:60]}...")
        else:
            filtered.append(filing)

    print(f"Filtered out {excluded_count} filings, {len(filtered)} remaining")
    return filtered


def deduplicate_filings(filings: list[SROFiling]) -> list[SROFiling]:
    """Remove duplicate filings based on URL."""
    seen_urls = set()
    unique = []

    for filing in filings:
        if filing.url not in seen_urls:
            seen_urls.add(filing.url)
            unique.append(filing)

    return unique


def generate_feed(filings: list[SROFiling], output_dir: Path) -> None:
    """Generate RSS and Atom feeds from filings."""
    fg = FeedGenerator()
    fg.id("https://github.com/edwinhu/sec-sro-rss")
    fg.title("SEC Self-Regulatory Organization Rulemaking")
    fg.subtitle("Filtered SEC SRO filings (excludes immediate effectiveness notices and crypto)")
    fg.link(href="https://www.sec.gov/rules-regulations/self-regulatory-organization-rulemaking", rel="alternate")
    fg.link(href="https://edwinhu.github.io/sec-sro-rss/feed.xml", rel="self")
    fg.language("en")
    fg.updated(datetime.now(timezone.utc))

    for filing in filings:
        fe = fg.add_entry()
        fe.id(filing.url)
        fe.title(filing.title)
        fe.link(href=filing.url)

        # Build description
        desc_parts = []
        if filing.source:
            desc_parts.append(f"Source: {filing.source.replace('-', ' ').title()}")
        if filing.date:
            desc_parts.append(f"Date: {filing.date}")
        if filing.description:
            desc_parts.append(filing.description)

        fe.description("\n".join(desc_parts) if desc_parts else filing.title)

        # Try to parse date, fall back to now
        if filing.date:
            try:
                # Try common date formats
                for fmt in ["%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y"]:
                    try:
                        dt = datetime.strptime(filing.date, fmt)
                        fe.published(dt.replace(tzinfo=timezone.utc))
                        fe.updated(dt.replace(tzinfo=timezone.utc))
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write feeds
    fg.rss_file(str(output_dir / "feed.xml"), pretty=True)
    fg.atom_file(str(output_dir / "atom.xml"), pretty=True)

    # Also save as JSON for debugging/alternative consumption
    filings_data = [
        {
            "id": f.id,
            "title": f.title,
            "url": f.url,
            "date": f.date,
            "description": f.description,
            "source": f.source,
        }
        for f in filings
    ]

    with open(output_dir / "filings.json", "w") as f:
        json.dump({
            "updated": datetime.now(timezone.utc).isoformat(),
            "count": len(filings_data),
            "filings": filings_data,
        }, f, indent=2)

    print(f"Generated feeds in {output_dir}")
    print(f"  - feed.xml (RSS 2.0)")
    print(f"  - atom.xml (Atom 1.0)")
    print(f"  - filings.json")


def main():
    """Main entry point."""
    output_dir = Path("docs")  # GitHub Pages serves from /docs

    print("=" * 60)
    print("SEC SRO Rulemaking RSS Feed Generator")
    print("=" * 60)

    # Scrape pages
    print("\n1. Scraping SEC SRO pages...")
    filings = scrape_all_pages(max_pages=3)
    print(f"   Total filings scraped: {len(filings)}")

    # Deduplicate
    print("\n2. Removing duplicates...")
    filings = deduplicate_filings(filings)
    print(f"   Unique filings: {len(filings)}")

    # Filter
    print("\n3. Filtering excluded content...")
    filings = filter_filings(filings)

    # Generate feed
    print("\n4. Generating feeds...")
    generate_feed(filings, output_dir)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
