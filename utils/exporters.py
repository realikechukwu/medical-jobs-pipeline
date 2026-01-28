import csv
import json
from datetime import datetime
from pathlib import Path


def save_to_json(jobs: list, filename: str | Path, metadata: dict = None):
    """Save jobs to JSON file"""
    output = {
        "metadata": {
            "scraped_at": datetime.now().isoformat(),
            "total_jobs": len(jobs),
            **(metadata or {})
        },
        "jobs": jobs
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved {len(jobs)} jobs to {filename}")


def save_to_csv(jobs: list, filename: str | Path, fieldnames: list = None):
    """Save jobs to CSV file"""
    if not jobs:
        print("No jobs to save!")
        return
    
    if not fieldnames:
        fieldnames = list(jobs[0].keys())
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(jobs)
    
    print(f"💾 Saved {len(jobs)} jobs to {filename}")


def calculate_field_completion(jobs: list, fields_to_track: list = None) -> dict:
    """Calculate field completion rates"""
    if not jobs:
        return {}
    
    if not fields_to_track:
        fields_to_track = [
            'title', 'company', 'location', 'salary', 'job_type',
            'description', 'requirements', 'responsibilities',
            'how_to_apply', 'deadline', 'email', 'phone'
        ]
    
    total_jobs = len(jobs)
    field_counts = {field: 0 for field in fields_to_track}
    
    for job in jobs:
        for field in fields_to_track:
            value = job.get(field, '')
            if value and str(value).strip() and str(value).strip().lower() != 'n/a':
                field_counts[field] += 1
    
    field_completion = {}
    for field, count in field_counts.items():
        percentage = (count / total_jobs) * 100 if total_jobs > 0 else 0
        field_completion[field] = {
            'count': count,
            'total': total_jobs,
            'percentage': round(percentage, 1)
        }
    
    return field_completion


def print_field_completion(field_completion: dict):
    """Print field completion rates"""
    print("\n" + "=" * 60)
    print("FIELD COMPLETION RATES")
    print("=" * 60)
    
    sorted_fields = sorted(
        field_completion.items(),
        key=lambda x: x[1]['percentage'],
        reverse=True
    )
    
    print(f"\n{'Field':<20} {'Count':<10} {'Rate':<10} {'Bar'}")
    print("-" * 60)
    
    for field, data in sorted_fields:
        count = data['count']
        total = data['total']
        percentage = data['percentage']
        bar_length = int(percentage / 5)
        bar = '█' * bar_length + '░' * (20 - bar_length)
        
        print(f"{field:<20} {count:>3}/{total:<5} {percentage:>5.1f}%   {bar}")