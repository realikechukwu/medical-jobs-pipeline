from pathlib import Path
import re

# Directories
ROOT_DIR = Path(__file__).parent
JSON_DIR = ROOT_DIR / "json"
OUTPUT_DIR = ROOT_DIR / "docs"

# Ensure directories exist
JSON_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Scraper settings
SCRAPER_CONFIG = {
    "medlocum": {
        "enabled": True,
        "rate_limit": 1.0,
        "max_pages": 4,
    },
    "jobsinnigeria": {
        "enabled": True,
        "rate_limit": 2.0,
        "max_pages": 4,
    },
    "medicalworldnigeria": {
        "enabled": True,
        "rate_limit": 2.0,
        "max_pages": 2,
        "professions": {"Doctors": 7, "Nurses": 14},
    },
}

# Extraction settings
EXTRACTION_CONFIG = {
    "model": "gpt-4o-mini",
    "max_age_days": 90,
    "max_jobs": 260,  # Limit OpenAI API calls
}

# Output files
OUTPUT_FILES = {
    "master_jobs": OUTPUT_DIR / "master_jobs.json",
    "raw_jobs": JSON_DIR / "raw_jobs.json", 
    
}


def clean_text(text: str) -> str:
    """Normalize whitespace and strip emails/URLs from text."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_url(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return bool(re.search(r"(https?://|www\.)", t)) or bool(re.fullmatch(r"\w+\.\w+/?\S*", t))


def has_protected_email(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    markers = [
        "email protected",
        "__cf_email__",
        "email-protection",
        "email redacted",
        "protected]",
    ]
    return any(m in t for m in markers)


def extract_apply_section(text: str) -> str:
    """Extract a slice after common application anchors."""
    if not text:
        return ""
    anchors = [
        "how to apply",
        "method of application",
        "application procedure",
        "application method",
    ]
    lowered = text.lower()
    for anchor in anchors:
        idx = lowered.find(anchor)
        if idx != -1:
            snippet = text[idx:idx + 2000]
            return clean_text(snippet)
    return ""


def extract_subject(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"subject\s*[:\-]\s*([^\n\r\.]+)",
        r"with the subject\s*[:\-]?\s*([^\n\r\.]+)",
        r"using the job title as the subject",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            if m.groups():
                return clean_text(m.group(1))[:120]
            return "Use the job title as the subject"
    return ""


def is_portal_apply(text: str, apply_url: str = "") -> bool:
    """Detect portal-based application via text or ATS URL patterns."""
    t = (text or "").lower()
    phrases = [
        "apply online",
        "apply through the link",
        "click here to apply",
        "application portal",
        "career portal",
        "apply now",
    ]
    if any(p in t for p in phrases):
        return True
    url = (apply_url or "").lower()
    ats_markers = [
        "workday",
        "myworkdayjobs",
        "greenhouse",
        "lever.co",
        "smartrecruiters",
        "icims",
        "taleo",
        "/apply",
    ]
    return any(m in url for m in ats_markers)


def normalize_how_to_apply(model_list, raw_job: dict, apply_url: str = "") -> list[str]:
    """Return 1-2 short bullets, no URLs/emails, consistent ending."""
    model_items = []
    if isinstance(model_list, list):
        model_items = [clean_text(x) for x in model_list if clean_text(x)]
    joined_model = " ".join(model_items)

    raw_content = raw_job.get("raw_content") or ""
    raw_text = clean_text(raw_content)
    apply_section = extract_apply_section(raw_content)
    source_text = apply_section or raw_text
    subject = extract_subject(source_text)

    protected = has_protected_email(raw_text) or has_protected_email(joined_model)

    has_email = bool(re.search(r"\bemail\b|e-mail", source_text, flags=re.IGNORECASE)) or protected
    has_phone = bool(re.search(r"\bwhatsapp\b|\bcall\b|\bphone\b", source_text, flags=re.IGNORECASE))
    has_portal = is_portal_apply(source_text, apply_url)
    has_apply_url = bool(apply_url)

    bullets = []

    if has_portal:
        bullets = [
            "Submit your application through the employer’s online recruitment portal.",
            "Click Apply Now for full details.",
        ]
    elif has_email:
        line = "Email the address shown on the original listing"
        if protected:
            line += " (email is protected on some sites)."
        else:
            line += "."
        if subject:
            line += f" Subject: {subject}."
        bullets.append(line)

    elif has_portal or has_apply_url:
        bullets.append("Apply via the Apply Now button for full details.")

    if not bullets:
        bullets.append("Click Apply Now for full details.")
    else:
        last = bullets[-1].lower()
        if "apply now" not in last and last != "click apply now for full details.":
            bullets.append("Click Apply Now for full details.")

    cleaned = []
    for b in bullets:
        b = clean_text(b)
        if not b or looks_like_url(b):
            continue
        if "email protected – see original listing" in b.lower():
            continue
        cleaned.append(b)
    return cleaned[:2] if cleaned else ["Click Apply Now for full details."]
