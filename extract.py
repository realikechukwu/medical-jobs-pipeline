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

from config import (
    JSON_DIR,
    OUTPUT_DIR,
    OUTPUT_FILES,
    EXTRACTION_CONFIG,
    normalize_how_to_apply,
    has_protected_email,
)


DATE_FORMATS = [
    "%d/%b/%Y",        # 25/Jan/2026
    "%d-%m-%Y",        # 23-01-2026
    "%d-%m-%Y - %a",   # 23-01-2026 - Fri
    "%d-%m-%Y - %A",   # 23-01-2026 - Friday
    "%Y-%m-%d",        # 2026-01-23
    "%d %B %Y",        # 27 January 2026
    "%d %b %Y",        # 27 Jan 2026
]

RELATIVE_DEADLINE_UNITS = {
    "day": 1,
    "days": 1,
    "week": 7,
    "weeks": 7,
    "month": 30,
    "months": 30,
}

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
}


def parse_date(s: str):
    if not s:
        return None
    s = s.strip()
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.I)
    s = s.replace(",", "").strip().rstrip(".")
    s = re.sub(r"\s+", " ", s)
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


def _normalize_relative_deadline_text(text: str) -> str:
    cleaned = (text or "").strip().lower()

    # convert (6) -> 6
    cleaned = re.sub(r"\((\d+)\)", r"\1", cleaned)

    # punctuation + whitespace
    cleaned = cleaned.replace(",", " ").replace(".", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # number words -> digits
    for word, num in NUMBER_WORDS.items():
        cleaned = re.sub(rf"\b{re.escape(word)}\b", str(num), cleaned)

    # collapse duplicated numbers: "6 6 weeks" -> "6 weeks"
    cleaned = re.sub(r"\b(\d+)\s+\1\b", r"\1", cleaned)

    return cleaned


def parse_relative_deadline(text: str, anchor_date):
    if not text or not anchor_date:
        return None

    cleaned = _normalize_relative_deadline_text(text)

    match = re.search(r"\b(\d+)\s*(day|days|week|weeks|month|months)\b", cleaned)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    days = amount * RELATIVE_DEADLINE_UNITS.get(unit, 0)
    if days <= 0:
        return None

    return anchor_date + timedelta(days=days)


def load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2)


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
    if "midwife" in t or "midwifery" in t or "nurse" in t or "nursing" in t or "matron" in t:
        return "Nurse"
    if ("medical officer" in t or "doctor" in t or "physician" in t or
        "obstetrician" in t or "gynaecologist" in t or "gynecologist" in t or
        "general practitioner" in t or "oncology" in t):
        return "Doctor"
    if ("public health" in t or "program officer" in t or "programme officer" in t or
        "epidemiology" in t or "surveillance" in t or "health systems" in t or
        "health security" in t or "project officer" in t):
        return "Public Health"
    if ("director" in t or "manager" in t or "coordinator" in t or
        "provost" in t or "hse " in t or "quality officer" in t or
        "inventory" in t or "warehouse" in t):
        return "Healthcare Management"
    if ("physiotherapist" in t or "optometrist" in t or "therapist" in t or
        "radiographer" in t or "dietitian" in t or "nutritionist" in t):
        return "Allied Health"
    return ""

def deduplicate_jobs(jobs):
    """Remove duplicate jobs based on job_title + company match."""
    seen = set()
    unique_jobs = []

    for job in jobs:
        title = (job.get("job_title") or "").strip().lower()
        company = (job.get("company") or "").strip().lower()
        key = f"{title}|{company}"

        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    return unique_jobs

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
    cache_hits = 0

    print("=" * 65)
    print("  JOB DATA EXTRACTION (OpenAI)")
    print(f"  Model: {args.model}")
    print(f"  Cutoff: {cutoff} ({args.max_age_days} days)")
    print("=" * 65)

    jobs_list = list(iter_jobs(args.json_dir))
    cache_path = OUTPUT_DIR / "extraction_cache.json"
    cache = load_cache(cache_path)

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

        apply_url = job.get("link") or job.get("job_url") or job.get("apply_url") or ""
        if apply_url and apply_url in cache:
            cached = cache.get(apply_url, {})
            cached_data = cached.get("data")
            if isinstance(cached_data, dict):
                cached_data = dict(cached_data)
                cached_data["_source"] = job.get("_source", source_name)
                extracted.append(cached_data)
                processed += 1
                cache_hits += 1
                if processed % 10 == 0:
                    print(f"  Processed: {processed} jobs...")
                if args.max and processed >= args.max:
                    print(f"\n  Reached max limit: {args.max}")
                    break
                if args.sleep:
                    time.sleep(args.sleep)
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
                            "For job_category, choose one: Doctor, Nurse, Pharmacist, Medical Laboratory Scientist, Dentist, Public Health, Healthcare Management, Allied Health, Other. "
                            "If job title includes 'medical officer', 'obstetrician', 'gynaecologist', or 'general practitioner', choose Doctor. "
                            "If job title includes 'midwife', 'midwifery', or 'matron', choose Nurse. "
                            "If job title includes 'program officer', 'project officer', 'epidemiology', 'surveillance', 'public health', or 'health systems', choose Public Health. "
                            "If job title includes 'director', 'manager', 'coordinator', 'provost', or 'quality officer', choose Healthcare Management. "
                            "If job title includes 'physiotherapist', 'optometrist', or 'therapist', choose Allied Health. "
                            "Use job title/requirements to decide; default to Other if unclear. "
                            "how_to_apply must be 1-2 short bullets, never include raw URLs or emails, "
                            "and always end with 'Click the Apply Now button for full details.' "
                            "Never output 'Email protected – see original listing' as the whole how_to_apply. "
                            "If email is protected/redacted, do not infer an email; leave contact_email empty "
                            "and use wording like 'Email the address shown on the original listing (email is protected on some sites).' "
                            "If subject instructions exist (e.g., 'Subject: X' or 'use job title as subject'), capture that in how_to_apply "
                            "without emails/URLs. "
                            "If apply method is phone/WhatsApp, say: "
                            "'Open the listing via Apply Now to view the contact details and follow the call or WhatsApp instructions.' "
                            "If apply method is via portal/link, say: "
                            "'Apply via the Apply Now button for full details.' "
                            "If the text indicates email protection/redaction (e.g., '__cf_email__', "
                            "'email-protection', 'email protected', 'email redacted'), do not infer an email."
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
            deadline_date = parse_date(data.get("deadline") or "")
            if deadline_date:
                data["deadline"] = deadline_date.isoformat()
            else:
                relative_deadline = parse_relative_deadline(
                    data.get("deadline") or "",
                    d or parse_date(job.get("_scraped_at") or "") or parse_date(job.get("scraped_at") or ""),
                )
                if relative_deadline:
                    data["deadline"] = relative_deadline.isoformat()
            title_category = classify_job_category(data.get("job_title") or "")
            if title_category:
                data["job_category"] = title_category
            if not data.get("salary") and job.get("salary"):
                data["salary"] = str(job.get("salary"))
            if not data.get("apply_url"):
                data["apply_url"] = apply_url

            protected = has_protected_email(job.get("raw_content") or "")
            if protected:
                data["contact_email"] = ""

            data["how_to_apply"] = normalize_how_to_apply(
                model_list=data.get("how_to_apply"),
                raw_job=job,
                apply_url=data.get("apply_url") or "",
            )
            
            # Add source tracking
            data["_source"] = job.get("_source", source_name)

            extracted.append(data)
            processed += 1
            if data.get("apply_url"):
                cache[data["apply_url"]] = {"data": data}
            
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

    # Deduplicate jobs
    original_count = len(extracted)
    extracted = deduplicate_jobs(extracted)
    deduped_count = original_count - len(extracted)

    if deduped_count > 0:
        print(f"  🔄 Deduplicated: {deduped_count} duplicate(s) removed")

    # Save output
    args.out.parent.mkdir(parents=True, exist_ok=True)
    save_cache(cache_path, cache)

    output_data = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "model": args.model,
            "total_processed": processed,
            "duplicates_removed": deduped_count,
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
    print(f"  💾 Cache hits: {cache_hits}")
    print(f"  ⏭️  Skipped (old): {skipped_date}")
    print(f"  ⏭️  Skipped (empty): {skipped_empty}")
    print(f"  ❌ Errors: {errors}")
    print(f"\n  📄 Output: {args.out}")


if __name__ == "__main__":
    main()
