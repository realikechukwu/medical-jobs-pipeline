import re
import time
from bs4 import BeautifulSoup

from .base import BaseScraper
from config import SCRAPER_CONFIG
from utils import (
    NIGERIAN_LOCATIONS,
    extract_first_match,
    extract_email,
    extract_phone,
    extract_location,
    SALARY_PATTERNS,
    QUALIFICATION_PATTERNS,
    EXPERIENCE_PATTERNS,
    DEADLINE_PATTERNS,
    JOB_TYPE_PATTERNS,
)


class MedicalWorldNigeriaScraper(BaseScraper):
    name = "medicalworldnigeria"
    base_url = "https://medicalworldnigeria.com"
    
    def __init__(self):
        super().__init__()
        self.config = SCRAPER_CONFIG.get(self.name, {})
        self.rate_limit = self.config.get('rate_limit', 2.0)
        self.max_pages = self.config.get('max_pages', 4)
        self.professions = self.config.get('professions', {"Doctors": 7, "Nurses": 14})
    
    def scrape_listing_page(self, url: str) -> list[dict]:
        """Get job links from listing page"""
        html = self.get_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        
        for card in soup.find_all('div', class_='newz'):
            try:
                link_tag = card.find('h5').find('a')
                date_tag = card.find('p', class_='post_date')
                
                jobs.append({
                    'title': link_tag.text.strip(),
                    'link': link_tag['href'],
                    'date_posted': date_tag.text.replace('Posted on:', '').strip() if date_tag else ''
                })
            except:
                continue
        
        return jobs
    
    def scrape_job_details(self, url: str) -> dict:
        """Extract full details from individual job page"""
        html = self.get_page(url)
        if not html:
            return {}
        
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.find('div', class_='single-page-content')
        
        if not content:
            return {}
        
        full_text = content.get_text(separator='\n', strip=True)
        
        details = {
            'description': '',
            'location': '',
            'salary': '',
            'requirements': '',
            'responsibilities': '',
            'how_to_apply': '',
            'deadline': '',
            'experience': '',
            'qualification': '',
            'job_type': '',
            'company': '',
            'email': '',
            'phone': '',
            'website': '',
            'raw_content': full_text[:5000],
        }
        
        # Description
        paragraphs = content.find_all('p')
        desc_parts = [p.get_text(strip=True) for p in paragraphs[:5] if p.get_text(strip=True)]
        if desc_parts:
            details['description'] = ' '.join(desc_parts)[:1500]
        
        # Use shared extractors
        details['location'] = extract_location(full_text, NIGERIAN_LOCATIONS)
        details['salary'] = extract_first_match(SALARY_PATTERNS, full_text)
        details['job_type'] = extract_first_match(JOB_TYPE_PATTERNS, full_text)
        details['experience'] = extract_first_match(EXPERIENCE_PATTERNS, full_text)
        details['qualification'] = extract_first_match(QUALIFICATION_PATTERNS, full_text)
        details['deadline'] = extract_first_match(DEADLINE_PATTERNS, full_text)
        details['email'] = extract_email(full_text)
        details['phone'] = extract_phone(full_text)
        
        # Company
        company_match = re.search(r'(?:company|organization|employer|hospital)[:\s]+([^\n]+)', full_text, re.IGNORECASE)
        if company_match:
            details['company'] = company_match.group(1).strip()[:200]
        
        # Requirements
        req_match = re.search(
            r'(?:requirements?|qualifications?\s*(?:and\s*experience)?)[:\s]*(.*?)(?=responsibilities|salary|method of application|how to apply|$)',
            full_text, re.IGNORECASE | re.DOTALL
        )
        if req_match and len(req_match.group(1).strip()) > 20:
            details['requirements'] = req_match.group(1).strip()[:2000]
        
        # Responsibilities
        resp_match = re.search(
            r'responsibilities?[:\s]*(.*?)(?=salary|requirements|method of application|how to apply|qualifications?|$)',
            full_text, re.IGNORECASE | re.DOTALL
        )
        if resp_match and len(resp_match.group(1).strip()) > 20:
            details['responsibilities'] = resp_match.group(1).strip()[:2000]
        
        # How to apply
        apply_match = re.search(
            r'(?:method of application|how to apply)[:\s]*(.*?)(?=note:|deadline|closing|$)',
            full_text, re.IGNORECASE | re.DOTALL
        )
        if apply_match and len(apply_match.group(1).strip()) > 10:
            details['how_to_apply'] = apply_match.group(1).strip()[:1000]
        
        # Website (exclude self)
        website_match = re.search(r'https?://[^\s<>"{}|\\^`]+', full_text)
        if website_match:
            url_found = website_match.group(0)
            if 'medicalworldnigeria' not in url_found:
                details['website'] = url_found
        
        return details
    
    def scrape_profession(self, profession_name: str, profession_id: int) -> list[dict]:
        """Scrape all jobs for a profession"""
        url_template = f"https://medicalworldnigeria.com/posts-by-profession/{profession_id}?page={{}}"
        
        print(f"\n📋 [{profession_name}] Collecting job links...")
        job_links = []
        
        for page in range(1, self.max_pages + 1):
            print(f"  Page {page}/{self.max_pages}...", end=" ")
            jobs = self.scrape_listing_page(url_template.format(page))
            
            if not jobs:
                print("No more jobs.")
                break
            
            job_links.extend(jobs)
            print(f"✅ {len(jobs)} jobs")
            time.sleep(1)
        
        print(f"📊 Total links: {len(job_links)}")
        print(f"🔍 [{profession_name}] Fetching details...")
        
        all_jobs = []
        for i, job in enumerate(job_links, 1):
            print(f"  [{i}/{len(job_links)}] {job['title'][:40]}...", end=" ")
            
            details = self.scrape_job_details(job['link'])
            
            if details:
                full_job = {
                    'title': job['title'],
                    'company': details.get('company', ''),
                    'location': details.get('location', ''),
                    'job_type': details.get('job_type', ''),
                    'salary': details.get('salary', ''),
                    'posted_date': job.get('date_posted', ''),
                    'deadline': details.get('deadline', ''),
                    'description': details.get('description', ''),
                    'requirements': details.get('requirements', ''),
                    'responsibilities': details.get('responsibilities', ''),
                    'how_to_apply': details.get('how_to_apply', ''),
                    'experience': details.get('experience', ''),
                    'qualification': details.get('qualification', ''),
                    'email': details.get('email', ''),
                    'phone': details.get('phone', ''),
                    'website': details.get('website', ''),
                    'raw_content': details.get('raw_content', ''),
                    'link': job['link'],
                    'profession': profession_name,
                }
                all_jobs.append(self._add_metadata(full_job))
                print("✅")
            else:
                print("⚠️ Skipped")
            
            time.sleep(self.rate_limit)
        
        return all_jobs
    
    def run(self) -> list[dict]:
        """Main entry point"""
        all_jobs = []
        
        for name, prof_id in self.professions.items():
            jobs = self.scrape_profession(name, prof_id)
            all_jobs.extend(jobs)
            print(f"\n✅ {name}: {len(jobs)} jobs")
            time.sleep(3)
        
        print(f"\n✅ Total: {len(all_jobs)} jobs")
        return all_jobs