import json
import re
import html
from datetime import datetime

from .base import BaseScraper
from config import SCRAPER_CONFIG


class MedLocumScraper(BaseScraper):
    name = "medlocum"
    base_url = "https://medlocumjobs.com/jobs"
    
    def __init__(self):
        super().__init__()
        self.config = SCRAPER_CONFIG.get(self.name, {})
    
    def clean_html(self, text: str) -> str:
        """Remove HTML tags and clean up text"""
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def fetch_all_pages(self) -> list[dict]:
        """Fetch jobs from all pages"""
        all_jobs = []
        page = 1
        max_pages = self.config.get('max_pages')
        
        while True:
            if max_pages and page > max_pages:
                break
            
            url = f"{self.base_url}?page={page}"
            print(f"  Fetching page {page}...")
            
            html_content = self.get_page(url)
            if not html_content:
                break
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            app_div = soup.find('div', {'id': 'app'})
            
            if not app_div or not app_div.get('data-page'):
                print("  Could not find data-page attribute")
                break
            
            try:
                page_data = json.loads(app_div['data-page'])
                jobs_data = page_data.get('props', {}).get('jobs', {})
                jobs_raw = jobs_data.get('data', [])
                
                if not jobs_raw:
                    print(f"  No jobs found on page {page}")
                    break
                
                print(f"  Found {len(jobs_raw)} jobs on page {page}")
                all_jobs.extend(jobs_raw)
                
                current_page = jobs_data.get('current_page', 1)
                last_page = jobs_data.get('last_page', 1)
                
                if current_page >= last_page:
                    break
                
                page += 1
                
            except json.JSONDecodeError as e:
                print(f"  JSON parse error: {e}")
                break
        
        return all_jobs
    
    def process_job(self, job: dict) -> dict:
        """Process a single job into standardized format"""
        # Build location string
        location_parts = []
        if job.get('location'):
            location_parts.append(job.get('location'))
        if job.get('state') and isinstance(job.get('state'), dict):
            state_name = job['state'].get('name', '')
            if state_name and state_name not in job.get('location', ''):
                location_parts.append(state_name)
        if job.get('country') and isinstance(job.get('country'), dict):
            location_parts.append(job['country'].get('name', ''))
        
        location = ', '.join(filter(None, location_parts))
        
        # Build salary string
        salary = job.get('formatted_salary', '')
        if not salary:
            salary_parts = []
            if job.get('salary_min'):
                salary_parts.append(f"{job.get('salary_currency', '')} {job.get('salary_min')}")
            if job.get('salary_max'):
                salary_parts.append(f"{job.get('salary_currency', '')} {job.get('salary_max')}")
            if salary_parts:
                salary = ' - '.join(salary_parts)
                if job.get('salary_period'):
                    salary += f" / {job.get('salary_period')}"
        
        # Build contact info
        contact_parts = []
        if job.get('contact_email'):
            contact_parts.append(f"Email: {job.get('contact_email')}")
        if job.get('contact_phone'):
            contact_parts.append(f"Phone: {job.get('contact_phone')}")
        
        # Format dates
        deadline = ''
        if job.get('application_deadline'):
            try:
                deadline_dt = datetime.fromisoformat(job['application_deadline'].replace('Z', '+00:00'))
                deadline = deadline_dt.strftime('%Y-%m-%d')
            except:
                deadline = job.get('application_deadline', '')
        
        posted_date = ''
        if job.get('created_at'):
            try:
                posted_dt = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                posted_date = posted_dt.strftime('%Y-%m-%d')
            except:
                posted_date = job.get('created_at', '')
        
        # Clean text fields
        description = self.clean_html(job.get('description', ''))
        requirements = self.clean_html(job.get('requirements', ''))
        responsibilities = self.clean_html(job.get('responsibilities', ''))
        
        # Build raw content
        raw_parts = []
        if description:
            raw_parts.append(f"DESCRIPTION:\n{description}")
        if responsibilities:
            raw_parts.append(f"RESPONSIBILITIES:\n{responsibilities}")
        if requirements:
            raw_parts.append(f"REQUIREMENTS:\n{requirements}")
        
        return {
            'title': job.get('title', ''),
            'company': job.get('company_name', ''),
            'location': location,
            'state': job.get('state', {}).get('name', '') if isinstance(job.get('state'), dict) else '',
            'country': job.get('country', {}).get('name', '') if isinstance(job.get('country'), dict) else '',
            'job_type': job.get('formatted_job_type', job.get('job_type', '')),
            'salary': salary,
            'posted_date': posted_date,
            'deadline': deadline,
            'description': description,
            'requirements': requirements,
            'responsibilities': responsibilities,
            'how_to_apply': '',
            'email': job.get('contact_email', ''),
            'phone': job.get('contact_phone', ''),
            'website': job.get('contact_website', ''),
            'contact_info': ' | '.join(contact_parts),
            'raw_content': '\n\n'.join(raw_parts),
            'link': f"https://medlocumjobs.com/jobs/{job.get('slug', '')}",
        }
    
    def run(self) -> list[dict]:
        """Main entry point"""
        print(f"\n📋 Fetching jobs from {self.base_url}")
        
        raw_jobs = self.fetch_all_pages()
        print(f"\n📊 Total raw jobs: {len(raw_jobs)}")
        
        processed = []
        for job in raw_jobs:
            processed_job = self.process_job(job)
            processed.append(self._add_metadata(processed_job))
        
        print(f"✅ Processed {len(processed)} jobs")
        return processed