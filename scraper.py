#!/usr/bin/env python3
"""
SEC SRO Rulemaking RSS Feed Generator

Uses the Federal Register API to fetch SEC Self-Regulatory Organization
notices, then generates an RSS feed, filtering out:
- "Notice of Filing and Immediate Effectiveness" items
- Crypto/digital asset related listings

The Federal Register API is reliable and doesn't block cloud IPs like SEC.gov does.
"""

import re
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import requests
from feedgen.feed import FeedGenerator

# Federal Register API endpoint
# Docs: https://www.federalregister.gov/developers/documentation/api/v1
FR_API_BASE = "https://www.federalregister.gov/api/v1"

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

USER_AGENT = "sec-sro-rss/1.0 (https://github.com/edwinhu/sec-sro-rss)"


class SROFiling(NamedTuple):
    """Represents a single SRO filing."""
    title: str
    url: str
    date: str
    description: str
    source: str

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


def fetch_federal_register_documents() -> list[SROFiling]:
    """Fetch SEC SRO documents from Federal Register API.

    We search for SEC notices with "Self-Regulatory Organizations" in the title.
    The API returns documents in JSON format with all metadata we need.
    """
    filings = []
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # Search parameters for SEC SRO notices
    # - agencies[]: securities-and-exchange-commission
    # - type[]: NOTICE
    # - term: "Self-Regulatory Organizations"
    # - per_page: 100 (max)
    # - order: newest

    params = {
        "conditions[agencies][]": "securities-and-exchange-commission",
        "conditions[type][]": "NOTICE",
        "conditions[term]": "Self-Regulatory Organizations",
        "per_page": 100,
        "order": "newest",
        "fields[]": [
            "title",
            "document_number",
            "html_url",
            "pdf_url",
            "publication_date",
            "abstract",
            "agencies",
        ],
    }

    url = f"{FR_API_BASE}/documents.json"
    print(f"Fetching from Federal Register API...")
    print(f"  URL: {url}")

    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"Error fetching from Federal Register: {e}")
        return []

    results = data.get("results", [])
    print(f"  Found {len(results)} documents")

    for doc in results:
        title = doc.get("title", "")
        html_url = doc.get("html_url", "")
        pdf_url = doc.get("pdf_url", "")
        pub_date = doc.get("publication_date", "")
        abstract = doc.get("abstract", "") or ""
        doc_number = doc.get("document_number", "")

        # Determine SRO source from title
        source = "national-securities-exchanges"
        if "FINRA" in title or "Financial Industry Regulatory Authority" in title:
            source = "finra"

        filing = SROFiling(
            title=title,
            url=html_url or pdf_url,
            date=pub_date,
            description=abstract,
            source=source,
        )
        filings.append(filing)

    return filings


def scrape_all_pages(max_pages: int = 3) -> list[SROFiling]:
    """Fetch filings from Federal Register API."""
    return fetch_federal_register_documents()


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

    # Fetch from Federal Register API
    print("\n1. Fetching from Federal Register API...")
    filings = scrape_all_pages(max_pages=3)
    print(f"   Total filings fetched: {len(filings)}")

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
