from pathlib import Path

# Directories
ROOT_DIR = Path(__file__).parent
JSON_DIR = ROOT_DIR / "json"
OUTPUT_DIR = ROOT_DIR / "output"

# Ensure directories exist
JSON_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Scraper settings
SCRAPER_CONFIG = {
    "medlocum": {
        "enabled": True,
        "rate_limit": 1.0,
        "max_pages": 2,
    },
    "jobsinnigeria": {
        "enabled": True,
        "rate_limit": 3.0,
        "max_pages": 2,
    },
    "medicalworldnigeria": {
        "enabled": True,
        "rate_limit": 2.0,
        "max_pages": 1,
        "professions": {"Doctors": 7, "Nurses": 14},
    },
}

# Extraction settings
EXTRACTION_CONFIG = {
    "model": "gpt-4o-mini",
    "max_age_days": 61,
    "max_jobs": 70,  # Limit OpenAI API calls
}

# Output files
OUTPUT_FILES = {
    "master_jobs": OUTPUT_DIR / "master_jobs.json",
}