import json
import re
import time
from bs4 import BeautifulSoup

from .base import BaseScraper
from config import SCRAPER_CONFIG
from utils import (
    NIGERIAN_LOCATIONS,
    clean_ad_content,
    extract_emails_safely,
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


class JobsInNigeriaScraper(BaseScraper):
    name = "jobsinnigeria"
    base_url = "https://jobsinnigeria.careers"
    category_url = "https://jobsinnigeria.careers/job-category/healthcaremedical-jobs-in-nigeria"
    
    def __init__(self):
        super().__init__()
        self.config = SCRAPER_CONFIG.get(self.name, {})
        self.rate_limit = self.config.get('rate_limit', 6.0)
        self.max_pages = self.config.get('max_pages', 5)
    
    def scrape_listing_page(self, url: str) -> list[dict]:
        """Get job links from listing page"""
        html = self.get_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        
        job_elements = soup.select('ol.jobs li.job, ol.jobs li.job-alt')
        
        for job_elem in job_elements:
            try:
                title_elem = job_elem.select_one('div#titlo strong a')
                if not title_elem:
                    continue
                
                type_elem = job_elem.select_one('div#type-tag span.jtype')
                location_elem = job_elem.select_one('div#location')
                date_elem = job_elem.select_one('div#date span.year')
                desc_elem = job_elem.select_one('div#exc div.lista')
                
                jobs.append({
                    'title': title_elem.text.strip(),
                    'link': title_elem.get('href'),
                    'employment_type': type_elem.text.strip() if type_elem else '',
                    'location_listing': location_elem.text.replace('Location:', '').strip() if location_elem else '',
                    'date_posted': date_elem.text.strip() if date_elem else '',
                    'snippet': desc_elem.text.strip()[:300] if desc_elem else '',
                })
            except Exception as e:
                continue
        
        return jobs
    
    def extract_from_json_ld(self, soup) -> dict:
        """Extract job details from JSON-LD structured data"""
        details = {}
        
        json_ld = soup.find('script', type='application/ld+json')
        if not json_ld:
            return details
        
        try:
            data = json.loads(json_ld.string)
            
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') == 'JobPosting':
                        data = item
                        break
                else:
                    return details
            
            if data.get('@type') != 'JobPosting':
                return details
            
            details['description'] = data.get('description', '')
            details['date_posted'] = data.get('datePosted', '')
            details['deadline'] = data.get('validThrough', '')
            details['job_type'] = data.get('employmentType', '')
            
            hiring_org = data.get('hiringOrganization', {})
            if isinstance(hiring_org, dict):
                details['company'] = hiring_org.get('name', '')
            
            job_location = data.get('jobLocation', {})
            if isinstance(job_location, dict):
                address = job_location.get('address', {})
                if isinstance(address, dict):
                    loc_parts = []
                    for key in ['streetAddress', 'addressLocality', 'addressRegion']:
                        if address.get(key):
                            loc_parts.append(address[key])
                    if loc_parts:
                        details['location'] = ', '.join(loc_parts)
            
            base_salary = data.get('baseSalary', {})
            if isinstance(base_salary, dict):
                currency = base_salary.get('currency', 'NGN')
                value_data = base_salary.get('value', {})
                if isinstance(value_data, dict):
                    min_val = value_data.get('minValue', '')
                    max_val = value_data.get('maxValue', '')
                    unit = value_data.get('unitText', 'MONTH')
                    if min_val and max_val:
                        details['salary'] = f"{currency} {min_val} - {max_val} per {unit.lower()}"
        except:
            pass
        
        return details
    
    def scrape_job_details(self, url: str) -> dict:
        """Extract full details from individual job page"""
        html = self.get_page(url)
        if not html:
            return {}

        email_safety = extract_emails_safely(html)
        
        soup = BeautifulSoup(html, 'html.parser')
        soup = clean_ad_content(soup)
        
        content = (
            soup.find('div', class_='single-page-content') or
            soup.find('article') or
            soup.find('div', id='mainContent') or
            soup.find('body')
        )
        
        full_text = content.get_text(separator='\n', strip=True) if content else ''
        
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
            'email_protected': email_safety.get('email_protected', False),
            'raw_content': full_text[:5000],
        }

        if email_safety.get('email_protected'):
            details['how_to_apply'] = email_safety.get('apply_text') or ''
        
        # Extract from JSON-LD first
        json_ld_data = self.extract_from_json_ld(soup)
        details.update({k: v for k, v in json_ld_data.items() if v})
        
        # Fill gaps with regex extraction
        if not details['description'] and content:
            paragraphs = content.find_all('p')
            desc_parts = [p.get_text(strip=True) for p in paragraphs[:10] if p.get_text(strip=True)]
            if desc_parts:
                details['description'] = ' '.join(desc_parts)[:3000]
        
        if not details['location']:
            details['location'] = extract_location(full_text, NIGERIAN_LOCATIONS)
        
        if not details['salary']:
            details['salary'] = extract_first_match(SALARY_PATTERNS, full_text)
        
        if not details['job_type']:
            details['job_type'] = extract_first_match(JOB_TYPE_PATTERNS, full_text)
        
        if not details['experience']:
            details['experience'] = extract_first_match(EXPERIENCE_PATTERNS, full_text)
        
        if not details['qualification']:
            details['qualification'] = extract_first_match(QUALIFICATION_PATTERNS, full_text)
        
        if not details['deadline']:
            details['deadline'] = extract_first_match(DEADLINE_PATTERNS, full_text)
        
        if not details['email'] and not details.get('email_protected'):
            details['email'] = extract_email(full_text)
        
        if not details['phone']:
            details['phone'] = extract_phone(full_text)
        
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
        if not details.get('email_protected'):
            apply_match = re.search(
                r'(?:method of application|how to apply)[:\s]*(.*?)(?=note:|deadline|closing|$)',
                full_text, re.IGNORECASE | re.DOTALL
            )
            if apply_match and len(apply_match.group(1).strip()) > 10:
                details['how_to_apply'] = apply_match.group(1).strip()[:1000]
        
        return details
    
    def run(self) -> list[dict]:
        """Main entry point"""
        print(f"\n📋 Collecting job links from {self.max_pages} pages...")
        
        job_links = []
        for page in range(1, self.max_pages + 1):
            url = self.category_url if page == 1 else f"{self.category_url}/page/{page}/"
            print(f"  Page {page}/{self.max_pages}...", end=" ")
            
            jobs = self.scrape_listing_page(url)
            if not jobs:
                print("No more jobs.")
                break
            
            job_links.extend(jobs)
            print(f"✅ {len(jobs)} jobs")
            
            if page < self.max_pages:
                time.sleep(self.rate_limit)
        
        print(f"\n📊 Total links: {len(job_links)}")
        print(f"🔍 Fetching details...")
        
        all_jobs = []
        for i, job in enumerate(job_links, 1):
            print(f"  [{i}/{len(job_links)}] {job['title'][:40]}...", end=" ")
            
            details = self.scrape_job_details(job['link'])
            
            full_job = {
                'title': job['title'],
                'company': details.get('company', ''),
                'location': details.get('location') or job.get('location_listing', ''),
                'job_type': details.get('job_type') or job.get('employment_type', ''),
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
                'email_protected': details.get('email_protected', False),
                'raw_content': details.get('raw_content', ''),
                'link': job['link'],
            }
            
            all_jobs.append(self._add_metadata(full_job))
            print("✅")
            
            if i < len(job_links):
                time.sleep(self.rate_limit)
        
        print(f"✅ Scraped {len(all_jobs)} jobs")
        return all_jobs
