from abc import ABC, abstractmethod
from datetime import datetime
import requests


class BaseScraper(ABC):
    """Base class for all scrapers"""
    
    name: str = "base"
    base_url: str = ""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def get_page(self, url: str, timeout: int = 30) -> str | None:
        """Fetch a page with error handling"""
        try:
            response = self.session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.text
            else:
                print(f"    Status {response.status_code} for {url}")
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
        return None
    
    @abstractmethod
    def run(self) -> list[dict]:
        """Main entry point - returns list of job dicts"""
        pass
    
    def _add_metadata(self, job: dict) -> dict:
        """Add standard metadata to a job"""
        job['_source'] = self.name
        job['_scraped_at'] = datetime.now().isoformat()
        return job