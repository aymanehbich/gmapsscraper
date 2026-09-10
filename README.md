# Google Maps Scraper Orchestrator

An automated, optimized system to scrape Google Maps niche-by-niche and organize results by Country and City automatically.

---

## Prerequisites
Make sure **Docker Desktop** is open and running on your computer.

---

## How to Run the Scraper

Open your terminal in this directory and choose one of the following methods:

### Method A: Interactive Wizard (Recommended)
This guides you step-by-step to choose a niche (from a numbered list), select a city/country, and configure options without typing commands:
```bash
python interactive_run.py
```

### Method B: Direct Command Line (Advanced)
Run direct CLI arguments using Python:

#### 1. Scrape a Specific Niche in a Specific City (Fastest & Safest)
To scrape only one city (e.g., **Geneva** or **Austin**):
```bash
python run_scraper.py --niche "Dentist" --city "Geneva"
```
```bash
python run_scraper.py --niche "Plumber" --city "Austin"
```
*Note: The `--city` filter is case-insensitive and works as a search (e.g., `Austin` matches `Austin TX` in `targets.json`).*

### 2. Scrape a Specific Niche across All Cities
To scrape all target countries and cities configured in `targets.json` for a specific niche:
```bash
python run_scraper.py --niche "Plumber"
```

### 3. Run with a Proxy File (Recommended for High Volume)
If you have a proxy list file (e.g., `proxies.txt` with one proxy URL per line), you can pass it to protect your IP from Google rate limits:
```bash
python run_scraper.py --niche "Plumber" --proxy-file "proxies.txt"
```

### 4. Customize Search Depth
By default, the script scrolls up to 30 times (`--depth 30`). To scrape a smaller set or speed things up, you can lower it:
```bash
python run_scraper.py --niche "Electrician" --depth 15
```

---

## CLI Options

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--niche` | **(Required)** Niche name matching one in `niches.json` | None |
| `--city` | Limit the scrape to a specific city name | None |
| `--targets` | Path to targets JSON config | `targets.json` |
| `--niches-file` | Path to niches JSON config | `niches.json` |
| `--depth` | Scroll depth | `30` |
| `--concurrency` | Number of concurrent search queries inside Docker | `4` |
| `--exit-on-inactivity`| Scraper timeout when no new items are found | `5m` |
| `--proxy` | Single proxy URL | None |
| `--proxy-file` | Path to a text file containing rotating proxies | None |
| `--keep-raw` | Keep the raw `raw_results.json` log file after cleaning | `False` |

---

## Output Folder Structure

Results are automatically saved and organized into your `output` folder:
`output/[Niche]/[Country]/[City]/cleaned_leads.json`

For example, running `--niche Dentist --city Geneva` creates:
```
output/
└── Dentist/
    └── Switzerland/
        └── Geneva/
            ├── cleaned_leads.json
            └── raw_results.json (Only if --keep-raw is used)
```

The output `cleaned_leads.json` will contain all unique leads, clean website/phone details, and user reviews capped to a maximum of 10.

---

## 📧 Email Enrichment (Post-Scrape Email Finder)

Since Google Maps scraping is done without crawling external websites for speed, you can enrich your existing `cleaned_leads.json` files with contact emails anytime.

### Option 1: Run Email Enrichment Automatically During Scrape
Add the `--enrich-emails` flag when running `run_scraper.py`:
```bash
py run_scraper.py --niche "Plumber" --city "Austin" --enrich-emails
```

### Option 2: Enrich Existing Workspace JSON Files (Standalone)
To recursively scan all `cleaned_leads.json` files in your `output/` folder and populate `"emails": [...]` in-place:
```bash
# Enrich all JSON lead files under output/
py modules/enrich_emails.py

# Or enrich a specific JSON file:
py modules/enrich_emails.py --file "output/Plumber/United_States/Austin_TX/cleaned_leads.json"
```

#### Enrichment Parameters
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `--dir` | Root output directory to search recursively | `output` |
| `--file` | Path to a single `cleaned_leads.json` file | None |
| `--threads` | Concurrent scraper threads | `12` |
| `--timeout` | HTTP timeout per website (seconds) | `7` |

---

## 📁 Workspace Structure

```
gmaps-scraper/
├── config/
│   ├── niches.json               # Niche keywords and language translations
│   └── targets.json              # Country and city target lists
├── modules/
│   ├── __init__.py
│   ├── clean_leads.py            # Deduplication & review-capping logic
│   └── enrich_emails.py          # Fast email crawler from business websites
├── output/                       # Scraped leads organized by Niche/Country/City
├── run_scraper.py                # Main orchestrator CLI
├── interactive_run.py            # Interactive terminal wizard
├── requirements.txt              # Project Python dependencies
├── .gitignore                    # Git ignore file
└── README.md
```


