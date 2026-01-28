#!/usr/bin/env python3
"""Run complete pipeline: Scrape → Extract"""

import subprocess
import sys
from datetime import datetime


def main():
    print("=" * 65)
    print("  MEDICAL JOBS PIPELINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    
    # Step 1: Scrape
    print("\n[STEP 1] SCRAPING...")
    result = subprocess.run([sys.executable, "main.py"])
    if result.returncode != 0:
        print("❌ Scraping failed")
        sys.exit(1)
    
    # Step 2: Extract
    print("\n[STEP 2] EXTRACTING...")
    result = subprocess.run([sys.executable, "extract.py"])
    if result.returncode != 0:
        print("❌ Extraction failed")
        sys.exit(1)
    
    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()