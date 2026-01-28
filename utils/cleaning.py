import re
import html as html_lib


def clean_html(text: str) -> str:
    """Remove HTML tags and clean up text"""
    if not text:
        return ""
    text = html_lib.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_ad_content(soup):
    """Remove ad-related elements from BeautifulSoup object"""
    ad_selectors = [
        '.adsbygoogle',
        'ins.adsbygoogle',
        'script',
        'style',
        'iframe',
        'noscript',
        '.ads',
        '.advertisement',
        '#floating_ads',
        '.floating_ads',
        '.wp-cookie-pro',
        '#wp-cookie-pro',
        '.cookie-consent',
        '.banner',
        '[class*="sponsor"]',
        '[class*="promo"]',
    ]
    
    for selector in ad_selectors:
        for element in soup.select(selector):
            element.decompose()
    
    for element in soup.find_all(class_=re.compile(r'ad[s]?[-_]?|banner|sponsor|promo', re.IGNORECASE)):
        element.decompose()
    
    return soup


def clean_raw_content(text: str) -> str:
    """Clean raw content by removing ad patterns"""
    ad_patterns = [
        r'adsbygoogle.*',
        r'Loading\.\.\.',
        r'Advertisement.*',
        r'Sponsored.*',
        r'cookies?.*consent.*',
        r'Subscribe.*newsletter.*',
        r'Share this.*',
        r'Facebook.*Twitter.*',
        r'Related\s+(?:Jobs|Posts).*',
    ]
    
    for pattern in ad_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


def extract_emails_safely(html: str) -> dict:
    """Detect protected emails in HTML (e.g., Cloudflare) and return safe defaults."""
    lowered = (html or "").lower()
    protected = ("cdn-cgi/l/email-protection" in lowered) or ("__cf_email__" in lowered)
    return {
        "emails": [] if protected else None,
        "email_protected": protected,
        "apply_text": "Email protected – see original listing" if protected else None,
    }
