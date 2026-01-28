#!/usr/bin/env python3
"""Extract and normalize job data using OpenAI"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from config import JSON_DIR, OUTPUT_DIR, OUTPUT_FILES, EXTRACTION_CONFIG


DATE_FORMATS = [
    "%d/%b/%Y",        # 25/Jan/2026
    "%d-%m-%Y",        # 23-01-2026
    "%d-%m-%Y - %a",   # 23-01-2026 - Fri
    "%d-%m-%Y - %A",   # 23-01-2026 - Friday
    "%Y-%m-%d",        # 2026-01-23
]


def parse_date(s: str):
    if not s:
        return None
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        pass
    if "T" in s:
        try:
            return datetime.fromisoformat(s.split("T", 1)[0]).date()
        except ValueError:
            pass
    return None


def pick_date(job: dict):
    for key in ("date_posted", "posted_date", "date", "scraped_at", "_scraped_at"):
        d = parse_date(job.get(key) or "")
        if d:
            return d, key
    return None, None


def build_text(job: dict) -> str:
    parts = []

    def add(label, value):
        if value and str(value).strip() and str(value).strip().lower() not in ('n/a', ''):
            parts.append(f"{label}: {value}")

    def sanitize(value: str) -> str:
        """Replace redacted email markers with a neutral instruction."""
        value = re.sub(r"(?i)\bemail\s*(?:is\s*)?redacted\b", "email to apply", value)
        value = re.sub(r"<email.*?protected>", "email to apply", value, flags=re.I)
        return value

    add("Title", job.get("title") or job.get("job_title"))
    add("Company", job.get("company_name") or job.get("company"))
    add("Location", job.get("location"))
    add("State", job.get("state"))
    add("Country", job.get("country"))
    add("Date Posted", job.get("date_posted") or job.get("posted_date"))
    add("Deadline", job.get("deadline"))
    add("Salary", job.get("salary"))
    add("Job Type", job.get("job_type") or job.get("employment_type"))
    add("Experience", job.get("experience"))
    add("Qualification", job.get("qualification"))
    add("Apply URL", job.get("link") or job.get("job_url"))
    add("Email Protected", job.get("email_protected"))

    for key in (
        "full_description",
        "description",
        "requirements",
        "responsibilities",
        "how_to_apply",
        "other_info",
        "raw_content",
    ):
        value = job.get(key)
        if isinstance(value, str) and value:
            value = sanitize(value)[:3000]
            add(key.replace("_", " ").title(), value)

    return "\n\n".join(parts)

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def response_text(response) -> str:
    text = _get(response, "output_text")
    if text:
        return text

    output_items = _get(response, "output", []) or []
    parts = []
    for item in output_items:
        if _get(item, "type") != "message":
            continue
        for chunk in _get(item, "content", []) or []:
            if _get(chunk, "type") == "output_text" and _get(chunk, "text"):
                parts.append(_get(chunk, "text"))
    if parts:
        return "\n".join(parts)
    raise ValueError("No output text in response")


def iter_jobs(json_dir: Path):
    """Iterate over jobs from raw_jobs.json only"""
    raw_jobs_file = json_dir / "raw_jobs.json"
    
    if not raw_jobs_file.exists():
        print(f"⚠️  {raw_jobs_file} not found. Run main.py first.")
        return
    
    try:
        with raw_jobs_file.open(encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for item in data:
                yield raw_jobs_file.name, item
        elif isinstance(data, dict):
            jobs = data.get("jobs", [])
            if isinstance(jobs, list):
                for item in jobs:
                    yield raw_jobs_file.name, item
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Error reading {raw_jobs_file.name}: {e}")

def classify_job_category(title: str) -> str:
    """Derive job category from title keywords when possible."""
    t = (title or "").strip().lower()
    if not t:
        return ""
    if "dentist" in t or "dental" in t:
        return "Dentist"
    if "medical laboratory" in t or ("laboratory" in t and "scientist" in t):
        return "Medical Laboratory Scientist"
    if "pharmacist" in t or "pharmacy" in t:
        return "Pharmacist"
    if "midwife" in t or "nurse" in t or "nursing" in t:
        return "Nurse"
    if "medical officer" in t or "doctor" in t or "physician" in t:
        return "Doctor"
    return ""

def main():
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY is not set.")
        print("   Add it to a .env file or set it as a GitHub secret.")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description="Extract job data using OpenAI")
    parser.add_argument("--json-dir", type=Path, default=JSON_DIR)
    parser.add_argument("--out", type=Path, default=OUTPUT_FILES["master_jobs"])
    parser.add_argument("--model", default=EXTRACTION_CONFIG["model"])
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--max", type=int, default=EXTRACTION_CONFIG.get("max_jobs", 0), help="Max jobs to process (0=all)")
    parser.add_argument("--today", default="")
    parser.add_argument("--max-age-days", type=int, default=EXTRACTION_CONFIG["max_age_days"])
    args = parser.parse_args()

    today = parse_date(args.today) if args.today else datetime.now().date()
    cutoff = today - timedelta(days=args.max_age_days)

    client = OpenAI()

    schema = {
        "type": "object",
        "properties": {
            "job_title": {"type": "string"},
            "company": {"type": "string"},
            "location": {"type": "string"},
            "job_type": {"type": "string"},
            "job_category": {"type": "string"},
            "salary": {"type": "string"},
            "experience": {"type": "string"},
            "qualification": {"type": "string"},
            "requirements": {"type": "array", "items": {"type": "string"}},
            "responsibilities": {"type": "array", "items": {"type": "string"}},
            "how_to_apply": {"type": "array", "items": {"type": "string"}},
            "date_posted": {"type": "string"},
            "deadline": {"type": "string"},
            "contact_email": {"type": "string"},
            "contact_phone": {"type": "string"},
            "apply_url": {"type": "string"},
        },
        "required": [
            "job_title", "company", "location", "job_type", "job_category", "salary",
            "experience", "qualification", "requirements", "responsibilities",
            "how_to_apply", "date_posted", "deadline", "contact_email", 
            "contact_phone", "apply_url",
        ],
        "additionalProperties": False,
    }

    extracted = []
    processed = 0
    skipped_date = 0
    skipped_empty = 0
    errors = 0

    print("=" * 65)
    print("  JOB DATA EXTRACTION (OpenAI)")
    print(f"  Model: {args.model}")
    print(f"  Cutoff: {cutoff} ({args.max_age_days} days)")
    print("=" * 65)

    jobs_list = list(iter_jobs(args.json_dir))

# Sort by date (newest first) so --max gets most recent jobs
    def get_date(item):
        source_name, job = item
        for key in ("date_posted", "posted_date", "date", "_scraped_at"):
            d = parse_date(job.get(key) or "")
            if d:
                return d
        return datetime.min.date()
    jobs_list.sort(key=get_date, reverse=True)

    total_jobs = len(jobs_list)
    print(f"\n📂 Found {total_jobs} jobs in {args.json_dir} (sorted newest first)")
    print(f"{'─' * 65}")

    for source_name, job in jobs_list:
        d, _ = pick_date(job)
        if d and d < cutoff:
            skipped_date += 1
            continue

        text = build_text(job)
        if not text.strip():
            skipped_empty += 1
            continue

        try:
            response = client.responses.create(
                model=args.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                    "Extract job fields from the text. Use only what is explicitly present. "
                    "If a field is missing, return an empty string or empty array as appropriate. "
                    "For location, include city and state/country if available. "
                    "For job_category, choose one: Doctor, Nurse, Pharmacist, Medical Laboratory Scientist, Dentist, Other. "
                    "If job title includes 'medical officer', choose Doctor. "
                    "If job title includes 'midwife', choose Nurse. "
                    "Use job title/requirements to decide; default to Other if unclear. "
                    "If the text indicates email protection/redaction (e.g., '__cf_email__', "
                    "'email-protection', 'email protected', 'email redacted'), do not infer an email; "
                    "leave contact_email empty and set how_to_apply to 'Email protected – see original listing' "
                    "only if no other application instructions are present."
                ),
                    },
                    {"role": "user", "content": text},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "job_extraction",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )

            data = json.loads(response_text(response))

            # Preserve/enhance certain fields
            if d:
                data["date_posted"] = d.isoformat()
            title_category = classify_job_category(data.get("job_title") or "")
            if title_category:
                data["job_category"] = title_category
            if not data.get("salary") and job.get("salary"):
                data["salary"] = str(job.get("salary"))
            if not data.get("apply_url"):
                data["apply_url"] = job.get("link") or job.get("job_url") or ""
            
            # Add source tracking
            data["_source"] = job.get("_source", source_name)

            extracted.append(data)
            processed += 1
            
            if processed % 10 == 0:
                print(f"  Processed: {processed} jobs...")

        except Exception as e:
            print(f"  ⚠️  Error processing job: {e}")
            errors += 1

        if args.max and processed >= args.max:
            print(f"\n  Reached max limit: {args.max}")
            break
        
        if args.sleep:
            time.sleep(args.sleep)

    # Save output
    args.out.parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "model": args.model,
            "total_processed": processed,
            "skipped_old": skipped_date,
            "skipped_empty": skipped_empty,
            "errors": errors,
        },
        "jobs": extracted,
    }
    
    with open(args.out, "w", encoding="utf-8") as out:
        json.dump(output_data, out, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'=' * 65}")
    print("  EXTRACTION COMPLETE")
    print(f"{'=' * 65}")
    print(f"  ✅ Processed: {processed}")
    print(f"  ⏭️  Skipped (old): {skipped_date}")
    print(f"  ⏭️  Skipped (empty): {skipped_empty}")
    print(f"  ❌ Errors: {errors}")
    print(f"\n  📄 Output: {args.out}")


if __name__ == "__main__":
    main()
