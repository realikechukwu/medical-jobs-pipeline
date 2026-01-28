#!/usr/bin/env python3
"""Main orchestrator - runs all scrapers"""

import argparse
import json
import sys
from datetime import datetime

from config import JSON_DIR, SCRAPER_CONFIG
from scrapers import MedLocumScraper, JobsInNigeriaScraper, MedicalWorldNigeriaScraper

SCRAPERS = {
    "medlocum": MedLocumScraper,
    "jobsinnigeria": JobsInNigeriaScraper,
    "medicalworldnigeria": MedicalWorldNigeriaScraper,
}


def run_scrapers(selected: list[str] = None):
    """Run scrapers and collect all jobs"""
    selected = selected or [name for name, cfg in SCRAPER_CONFIG.items() if cfg.get("enabled")]
    
    all_jobs = []
    results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("=" * 65)
    print("  MEDICAL JOBS SCRAPER PIPELINE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    
    for name in selected:
        if name not in SCRAPERS:
            print(f"⚠️  Unknown scraper: {name}")
            continue
        
        config = SCRAPER_CONFIG.get(name, {})
        if not config.get("enabled", True):
            print(f"⏭️  Skipping disabled scraper: {name}")
            continue
        
        print(f"\n{'─' * 65}")
        print(f"  RUNNING: {name.upper()}")
        print(f"{'─' * 65}")
        
        try:
            scraper = SCRAPERS[name]()
            jobs = scraper.run()
            all_jobs.extend(jobs)
            results[name] = {"status": "success", "count": len(jobs)}
            print(f"✅ {name}: {len(jobs)} jobs scraped")
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = {"status": "error", "error": str(e)}
    
    # Save combined output
    output_file = JSON_DIR / f"all_raw_jobs_{timestamp}.json"
    latest_file = JSON_DIR / "latest_raw_jobs.json"
    
    output_data = {
        "metadata": {
            "scraped_at": datetime.now().isoformat(),
            "sources": results,
            "total_jobs": len(all_jobs),
        },
        "jobs": all_jobs
    }
    
    for filepath in [output_file, latest_file]:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n" + "=" * 65)
    print("  SCRAPING COMPLETE")
    print("=" * 65)
    print(f"\n  Total jobs: {len(all_jobs)}")
    for name, result in results.items():
        status = "✅" if result["status"] == "success" else "❌"
        count = result.get("count", 0)
        print(f"  {status} {name}: {count} jobs")
    print(f"\n  Output: {output_file}")
    
    return all_jobs, results


def main():
    parser = argparse.ArgumentParser(description="Run medical job scrapers")
    parser.add_argument("scrapers", nargs="*", help="Specific scrapers to run (default: all)")
    args = parser.parse_args()
    
    jobs, results = run_scrapers(args.scrapers if args.scrapers else None)
    
    if any(r["status"] == "error" for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()