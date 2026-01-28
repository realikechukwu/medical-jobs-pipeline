import re

PHONE_PATTERNS = [
    r'(?:\+234|0)[789]\d{9}',
    r'(?:\+234|0)\s*[789]\d{2}[\s\-]?\d{3}[\s\-]?\d{4}',
    r'\d{4}[\s-]?\d{3}[\s-]?\d{4}',
]

SALARY_PATTERNS = [
    r'salary[:\s]+([^\n]+)',
    r'remuneration[:\s]+([^\n]+)',
    r'compensation[:\s]+([^\n]+)',
    r'(₦[\d,]+(?:\s*-\s*₦?[\d,]+)?(?:\s*per\s*\w+)?)',
    r'(NGN[\s]?[\d,]+(?:\s*-\s*[\d,]+)?)',
    r'(N[\d,]+(?:\s*-\s*N?[\d,]+)?(?:\s*per\s*\w+)?)',
    r'(\d{1,3}(?:,\d{3})+(?:\s*-\s*\d{1,3}(?:,\d{3})+)?)',
]

QUALIFICATION_PATTERNS = [
    r'(MBBS|M\.?B\.?B\.?S|B\.?Sc|M\.?Sc|Ph\.?D|HND|OND|RN|BNSc|Fellow|MDCN|Diploma|Bachelor|Master|Degree|BPharm|PharmD)',
    r'must possess[:\s]+([^\n]+)',
    r'educational qualification[:\s]+([^\n]+)',
    r'education[:\s]+([^\n]+)',
]

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

DEADLINE_PATTERNS = [
    r'application closing date[:\s]+([^\n]+)',
    r'closes?\s+(\d+\s*(?:weeks?|days?|months?)\s+from[^\.]+)',
    r'deadline[:\s]+([^\n]+)',
    r'closing date[:\s]+([^\n]+)',
    r'applications?\s+close[s]?\s+(?:on\s+)?([^\n\.]+)',
    r'expires?[:\s]+([^\n]+)',
    r'valid\s+(?:until|till)[:\s]+([^\n]+)',
    r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)[,]?\s+\d{4})',
    r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
]

EXPERIENCE_PATTERNS = [
    r'(\d+)\s*(?:\+)?\s*years?\s*(?:of\s+)?(?:experience|post[- ]?qualification)',
    r'(?:minimum|at least)\s+(\d+)\s*years?',
    r'experience[:\s]+([^\n]+)',
    r'(\d+\s*-\s*\d+)\s*years?\s*(?:of\s+)?experience',
    r'work experience[:\s]+([^\n]+)',
]

JOB_TYPE_PATTERNS = [
    r'job type[:\s]+([^\n]+)',
    r'employment type[:\s]+([^\n]+)',
    r'(full[- ]?time|part[- ]?time|contract|temporary|permanent|internship|remote|hybrid|locum|volunteer)',
]


def extract_first_match(patterns: list, text: str, flags=re.IGNORECASE) -> str:
    """Try each pattern and return first match"""
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip() if match.groups() else match.group(0).strip()
    return ""


def extract_email(text: str) -> str:
    """Extract email from text"""
    match = re.search(EMAIL_PATTERN, text)
    if match:
        email = match.group(0)
        if not any(x in email.lower() for x in ['example.com', 'test.com', 'email.com']):
            return email
    return ""


def extract_phone(text: str) -> str:
    """Extract Nigerian phone number from text"""
    for pattern in PHONE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def extract_location(text: str, locations_list: list) -> str:
    """Extract location from text"""
    # Try explicit location pattern first
    loc_match = re.search(r'location[:\s]+([^\n]+)', text, re.IGNORECASE)
    if loc_match:
        return loc_match.group(1).strip()[:100]
    
    # Fall back to searching for city/state names
    found = []
    for loc in locations_list:
        if re.search(r'\b' + re.escape(loc) + r'\b', text, re.IGNORECASE):
            found.append(loc)
    
    if found:
        return ', '.join(list(dict.fromkeys(found))[:3])
    
    return ""