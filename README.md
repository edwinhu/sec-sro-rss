# SEC SRO Rulemaking RSS Feed

Automatically generated RSS feed of SEC Self-Regulatory Organization (SRO) rulemaking filings.

## Feed URLs

- **RSS**: https://edwinhu.github.io/sec-sro-rss/feed.xml
- **Atom**: https://edwinhu.github.io/sec-sro-rss/atom.xml
- **JSON**: https://edwinhu.github.io/sec-sro-rss/filings.json

## Data Source

Uses the [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1) to fetch SEC notices with "Self-Regulatory Organizations" in the title. This covers all SROs including:

- National Securities Exchanges (NYSE, NASDAQ, CBOE, etc.)
- FINRA
- Clearing agencies (DTCC, OCC, etc.)

## Filters

The following are **excluded** from the feed:

1. **"Notice of Filing and Immediate Effectiveness"** - Routine filings that become effective immediately without a comment period
2. **Crypto/Digital Asset filings** - Bitcoin, Ethereum, and other cryptocurrency-related rule changes

## Setup (for forking)

1. Fork this repository
2. Enable GitHub Pages: Settings > Pages > Source: "GitHub Actions"
3. Replace `edwinhu` with your username in `scraper.py`, `docs/index.html`, and this README
4. The workflow runs every 6 hours automatically

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python scraper.py

# Output will be in docs/
```

## How It Works

1. GitHub Actions runs `scraper.py` every 6 hours
2. The scraper fetches the SEC SRO rulemaking pages
3. Filings are parsed, deduplicated, and filtered
4. RSS/Atom/JSON feeds are generated in `docs/`
5. Changes are committed and GitHub Pages deploys the updated feeds

## License

MIT
