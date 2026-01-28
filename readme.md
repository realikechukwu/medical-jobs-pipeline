# Medical Jobs Nigeria - Scraping Pipeline

## Overview

This pipeline automatically scrapes medical/healthcare job postings from three Nigerian job boards, normalizes the data using AI, and outputs a clean JSON file that can power a static website.

---

## How It Works (Step by Step)

### Step 1: Configuration (`config.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  CONFIGURATION                                               │
├─────────────────────────────────────────────────────────────┤
│  • Sets up directory paths (json/, docs/)                    │
│  • Defines which scrapers are enabled                        │
│  • Sets rate limits (delays between requests)                │
│  • Configures extraction settings (AI model, date cutoff)    │
└─────────────────────────────────────────────────────────────┘
```

**What it controls:**
| Setting | Purpose |
|---------|---------|
| `JSON_DIR` | Where raw scraped data is saved |
| `OUTPUT_DIR` | Where final processed data goes |
| `rate_limit` | Seconds to wait between requests (be polite to servers) |
| `max_pages` | How many listing pages to scrape per source |
| `max_age_days` | Only process jobs posted within X days |
| `max_jobs` | Max jobs to send to OpenAI per run (0 = all) |

---

### Step 2: Shared Utilities (`utils/`)

```
┌─────────────────────────────────────────────────────────────┐
│  UTILITIES (Shared Code)                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  locations.py    → List of Nigerian states/cities            │
│                    (Lagos, Abuja, Kano, etc.)                │
│                                                              │
│  patterns.py     → Regex patterns to extract:                │
│                    • Phone numbers (+234...)                 │
│                    • Salaries (₦, NGN)                       │
│                    • Emails                                  │
│                    • Deadlines                               │
│                    • Qualifications (MBBS, RN, etc.)         │
│                                                              │
│  cleaning.py     → Functions to:                             │
│                    • Remove HTML tags                        │
│                    • Strip advertisements                    │
│                    • Clean whitespace                        │
│                                                              │
│  exporters.py    → Functions to:                             │
│                    • Save to JSON                            │
│                    • Save to CSV                             │
│                    • Calculate field completion stats        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Why shared utilities?**
- All three scrapers need to extract Nigerian phone numbers → same regex
- All three scrapers need to find locations → same city list
- DRY principle: Don't Repeat Yourself

---

### Step 3: Scrapers (`scrapers/`)

Each scraper follows this pattern:

```
┌─────────────────────────────────────────────────────────────┐
│  SCRAPER WORKFLOW                                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. FETCH LISTING PAGES                                      │
│     ┌─────────────┐                                          │
│     │  Page 1     │ → Extract job titles + links             │
│     │  Page 2     │ → Extract job titles + links             │
│     │  Page 3     │ → Extract job titles + links             │
│     └─────────────┘                                          │
│            ↓                                                 │
│     List of 50-100 job URLs                                  │
│                                                              │
│  2. VISIT EACH JOB PAGE                                      │
│     ┌─────────────┐                                          │
│     │  Job URL    │ → Extract full details:                  │
│     │             │    • Title, Company                      │
│     │             │    • Location, Salary                    │
│     │             │    • Requirements                        │
│     │             │    • How to apply                        │
│     │             │    • Contact info                        │
│     └─────────────┘                                          │
│            ↓                                                 │
│     (wait 2-6 seconds - be polite!)                          │
│            ↓                                                 │
│     Next job URL...                                          │
│                                                              │
│  3. OUTPUT                                                   │
│     List of standardized job dictionaries                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Scraper 1: MedLocum (`medlocum.py`)

```
Source:     https://medlocumjobs.com
Focus:      Global medical/locum jobs
Method:     Extracts JSON embedded in HTML (data-page attribute)
Special:    No need to visit individual pages - all data in listing!
```

**How it extracts data:**
```
HTML Page
    ↓
<div id="app" data-page='{"props":{"jobs":{"data":[...]}}}'> 
    ↓
Parse JSON from data-page attribute
    ↓
Extract: title, company, salary, location, description, etc.
```

#### Scraper 2: Jobs In Nigeria (`jobsinnigeria.py`)

```
Source:     https://jobsinnigeria.careers
Focus:      Healthcare/Medical category
Method:     1. JSON-LD structured data (if available)
            2. Fallback to HTML parsing + regex
Special:    Removes ads/cookie banners before parsing
```

**Extraction priority:**
```
1. Try JSON-LD (structured data)  ← Most reliable
       ↓ (if missing)
2. Try explicit patterns          ← "Salary: ₦200,000"
       ↓ (if missing)  
3. Try regex patterns             ← Find ₦ followed by numbers
       ↓ (if missing)
4. Leave empty
```

#### Scraper 3: Medical World Nigeria (`medicalworldnigeria.py`)

```
Source:     https://medicalworldnigeria.com
Focus:      Doctors (ID: 7) and Nurses (ID: 14)
Method:     HTML parsing + regex
Special:    Organized by profession ID in URL
```

**URL structure:**
```
/posts-by-profession/7?page=1   → Doctors, page 1
/posts-by-profession/7?page=2   → Doctors, page 2
/posts-by-profession/14?page=1  → Nurses, page 1
```

---

### Step 4: Main Orchestrator (`main.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR                                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT: Command line arguments (optional)                    │
│         python main.py                    → Run all          │
│         python main.py medlocum           → Run one          │
│         python main.py medlocum jobsin... → Run specific     │
│                                                              │
│  PROCESS:                                                    │
│         ┌──────────────────┐                                 │
│         │  MedLocum        │ → 200 jobs                      │
│         ├──────────────────┤                                 │
│         │  JobsInNigeria   │ → 50 jobs                       │
│         ├──────────────────┤                                 │
│         │  MedicalWorld    │ → 80 jobs                       │
│         └──────────────────┘                                 │
│                  ↓                                           │
│         Combine all: 330 jobs                                │
│                  ↓                                           │
│         Add metadata (source, timestamp)                     │
│                                                              │
│  OUTPUT:                                                     │
│         json/raw_jobs.json                                   │
│         json/latest_raw_jobs.json (always current)           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Output structure:**
```json
{
  "metadata": {
    "scraped_at": "2025-01-15T12:00:00",
    "sources": {
      "medlocum": {"status": "success", "count": 200},
      "jobsinnigeria": {"status": "success", "count": 50},
      "medicalworldnigeria": {"status": "success", "count": 80}
    },
    "total_jobs": 330
  },
  "jobs": [
    {
      "title": "Registered Nurse",
      "company": "Lagos General Hospital",
      "location": "Lagos",
      "salary": "₦150,000 - ₦200,000",
      "requirements": "...",
      "_source": "medlocum",
      "_scraped_at": "2025-01-15T12:00:00"
    },
    // ... more jobs
  ]
}
```

---

### Step 5: AI Extraction (`extract.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  AI EXTRACTION (OpenAI)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PURPOSE: Clean & normalize messy scraped data               │
│                                                              │
│  INPUT:                                                      │
│  ┌─────────────────────────────────────────┐                 │
│  │ "Requirements: MBBS, 3yrs exp, MDCN     │                 │
│  │  license. Send CV to hr@hospital.com    │                 │
│  │  before 31st January 2025. Salary:      │                 │
│  │  200k-300k monthly..."                  │                 │
│  └─────────────────────────────────────────┘                 │
│                       ↓                                      │
│              OpenAI GPT-4o-mini                               │
│                       ↓                                      │
│  OUTPUT:                                                     │
│  ┌─────────────────────────────────────────┐                 │
│  │ {                                       │                 │
│  │   "job_title": "Medical Officer",       │                 │
│  │   "company": "General Hospital",        │                 │
│  │   "requirements": [                     │                 │
│  │     "MBBS degree",                      │                 │
│  │     "3 years experience",               │                 │
│  │     "MDCN license"                      │                 │
│  │   ],                                    │                 │
│  │   "how_to_apply": [                     │                 │
│  │     "Send CV to hr@hospital.com"        │                 │
│  │   ],                                    │                 │
│  │   "deadline": "2025-01-31",             │                 │
│  │   "salary": "₦200,000 - ₦300,000/month" │                 │
│  │ }                                       │                 │
│  └─────────────────────────────────────────┘                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Filtering logic:**
```
For each job in json/raw_jobs.json:
    │
    ├─ Is date older than 61 days? → SKIP
    │
    ├─ Is content empty? → SKIP
    │
    └─ Send to OpenAI → Extract structured fields
```

**Output schema (enforced by OpenAI):**
```json
{
  "job_title": "string",
  "company": "string", 
  "location": "string",
  "job_type": "string",
  "salary": "string",
  "requirements": ["string", "string"],
  "how_to_apply": ["string"],
  "date_posted": "string",
  "deadline": "string",
  "contact_email": "string",
  "contact_phone": "string"
}
```

---

### Step 6: Pipeline Runner (`run_pipeline.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  PIPELINE                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  python run_pipeline.py                                      │
│                                                              │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐                 │
│  │ SCRAPE  │ ──► │ EXTRACT │ ──► │ OUTPUT  │                 │
│  │ main.py │     │extract.py│    │  JSON   │                 │
│  └─────────┘     └─────────┘     └─────────┘                 │
│                                                              │
│  Runs both steps in sequence                                 │
│  Exits with error code if any step fails                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 7: GitHub Actions (`.github/workflows/weekly_scrape.yml`)

```
┌─────────────────────────────────────────────────────────────┐
│  AUTOMATION (GitHub Actions)                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  TRIGGER: Every Monday at 6:00 AM UTC                        │
│           OR manual trigger (workflow_dispatch)              │
│                                                              │
│  STEPS:                                                      │
│  ┌─────────────────────────────────────────┐                 │
│  │ 1. Checkout code                        │                 │
│  │ 2. Setup Python 3.11                    │                 │
│  │ 3. Install dependencies                 │                 │
│  │ 4. Run scrapers (main.py)               │                 │
│  │ 5. Run extraction (extract.py)          │                 │
│  │    └─ Uses OPENAI_API_KEY secret        │                 │
│  │ 6. Commit updated docs/master_jobs.json │                 │
│  └─────────────────────────────────────────┘                 │
│                                                              │
│  RESULT:                                                     │
│  docs/master_jobs.json updated in the repo                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────┘

     SOURCES                    SCRAPING                    PROCESSING
  ┌───────────┐              ┌───────────┐               ┌───────────┐
  │ MedLocum  │──────────────│           │               │           │
  │  .com     │              │           │               │           │
  └───────────┘              │           │               │           │
                             │   main.py │               │           │
  ┌───────────┐              │           │    json/      │ extract.py│
  │ JobsIn    │──────────────│  Scrape   │──────────────►│           │
  │ Nigeria   │              │  & Save   │  raw data     │  OpenAI   │
  └───────────┘              │           │               │  Cleanup  │
                             │           │               │           │
  ┌───────────┐              │           │               │           │
  │ Medical   │──────────────│           │               │           │
  │ World NG  │              │           │               │           │
  └───────────┘              └───────────┘               └─────┬─────┘
                                                               │
                                                               ▼
                                                        ┌───────────┐
                                                        │  docs/    │
                                                        │  master_  │
                                                        │  jobs.json│
                                                        └─────┬─────┘
                                                              │
                             ┌────────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                         GITHUB ACTIONS                               │
  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────────┐   │
  │  │ Weekly  │───►│  Run    │───►│ Commit  │───►│ Repo contains   │   │
  │  │ Trigger │    │ Pipeline│    │ updates │    │ docs/master_   │   │
  │  │ Mon 6AM │    │         │    │ to repo │    │ jobs.json       │   │
  │  └─────────┘    └─────────┘    └─────────┘    └────────┬────────┘   │
  └────────────────────────────────────────────────────────┼────────────┘
                                                           │
                                                           ▼
                                                    ┌─────────────┐
                                                    │   STATIC    │
                                                    │   WEBSITE   │
                                                    │  fetches    │
                                                    │  JSON API   │
                                                    └─────────────┘
```

---

## File Outputs

| File | Location | Purpose |
|------|----------|---------|
| `raw_jobs.json` | `json/` | Latest raw scrape (combined) |
| `latest_raw_jobs.json` | `json/` | Always-current raw data |
| `master_jobs.json` | `docs/` | Final cleaned data for website |

---

## Usage Examples

### Run Everything Locally
```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add OPENAI_API_KEY

# Run full pipeline
python run_pipeline.py
```

### Run Individual Steps
```bash
# Scrape only (no AI)
python main.py

# Scrape specific sources
python main.py medlocum
python main.py medlocum jobsinnigeria

# Extract only (requires existing json/ data)
python extract.py

# Extract with limits (for testing)
python extract.py --max 10
```

### GitHub Actions
```bash
# Runs automatically every Monday
# Or trigger manually:
# Actions → Weekly Job Scrape → Run workflow
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes (for extraction) | Your OpenAI API key |

**Local:** Add to `.env` file
**GitHub:** Add to Settings → Secrets → Actions

---

## Rate Limiting (Being Polite)

| Scraper | Delay | Reason |
|---------|-------|--------|
| MedLocum | 1 sec | Fast site, light delay |
| JobsInNigeria | 3 sec | Slower, respect their servers |
| MedicalWorld | 2 sec | Medium delay |

---

## Field Extraction Summary

| Field | MedLocum | JobsInNigeria | MedicalWorld |
|-------|----------|---------------|--------------|
| Title | ✅ JSON | ✅ HTML | ✅ HTML |
| Company | ✅ JSON | ✅ JSON-LD/regex | ✅ regex |
| Location | ✅ JSON | ✅ JSON-LD/city list | ✅ city list |
| Salary | ✅ JSON | ✅ JSON-LD/regex | ✅ regex |
| Requirements | ✅ JSON | ✅ regex | ✅ regex |
| Email | ✅ JSON | ✅ regex | ✅ regex |
| Phone | ✅ JSON | ✅ regex (Nigerian) | ✅ regex (Nigerian) |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `OPENAI_API_KEY not set` | Add key to `.env` or GitHub secrets |
| `No jobs found` | Website structure may have changed |
| `Rate limited` | Increase delay in `config.py` |
| `JSON parse error` | Website changed their data format |
| `GitHub Action fails` | Check Actions logs for specific error |

---

## License

MIT
