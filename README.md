# SEC SRO Rulemaking RSS Feed

Automatically generated RSS feed of SEC Self-Regulatory Organization (SRO) rulemaking filings.

## Feed URLs

Once deployed, the feeds will be available at:

- **RSS**: `https://YOUR_USERNAME.github.io/sec-sro-rss/feed.xml`
- **Atom**: `https://YOUR_USERNAME.github.io/sec-sro-rss/atom.xml`
- **JSON**: `https://YOUR_USERNAME.github.io/sec-sro-rss/filings.json`

## Sources

- [National Securities Exchanges](https://www.sec.gov/rules-regulations/self-regulatory-organization-rulemaking/national-securities-exchanges) (NYSE, NASDAQ, CBOE, etc.)
- [FINRA](https://www.sec.gov/rules-regulations/self-regulatory-organization-rulemaking/finra)

## Filters

The following are **excluded** from the feed:

1. **"Notice of Filing and Immediate Effectiveness"** - Routine filings that become effective immediately without a comment period
2. **Crypto/Digital Asset filings** - Bitcoin, Ethereum, and other cryptocurrency-related rule changes

## Setup

1. Fork this repository
2. Enable GitHub Pages:
   - Go to Settings > Pages
   - Set Source to "GitHub Actions"
3. Update placeholders:
   - Replace `YOUR_USERNAME` in `scraper.py`, `docs/index.html`, and this README with your GitHub username
4. The workflow will run automatically every 6 hours, or trigger manually via Actions tab

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
