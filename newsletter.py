#!/usr/bin/env python3
"""Send weekly job digest newsletter via Brevo"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


def load_jobs(filepath: Path, limit: int = 20) -> list:
    """Load and return top N jobs sorted by date."""
    if not filepath.exists():
        print(f"❌ {filepath} not found")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", []) if isinstance(data, dict) else data

    # Sort by date_posted descending (newest first)
    jobs.sort(key=lambda j: j.get("date_posted", ""), reverse=True)

    return jobs[:limit]


def format_date(date_str: str) -> str:
    """Format ISO date to readable format."""
    if not date_str:
        return "Date not specified"
    try:
        d = datetime.fromisoformat(date_str)
        return d.strftime("%d %b %Y")
    except ValueError:
        return date_str


def build_email_html(jobs: list) -> str:
    """Build HTML email content."""

    # Get date range for subject
    dates = [j.get("date_posted", "") for j in jobs if j.get("date_posted")]
    date_range = ""
    if dates:
        oldest = format_date(min(dates))
        newest = format_date(max(dates))
        date_range = f"{oldest} - {newest}"

    # Build job listings HTML
    job_rows = ""
    for i, job in enumerate(jobs, 1):
        title = job.get("job_title", "Untitled Role")
        company = job.get("company", "Company not listed")
        location = job.get("location", "")
        salary = job.get("salary", "")
        deadline = job.get("deadline", "")
        apply_url = job.get("apply_url", "https://jobbermed.com")

        meta_parts = [company]
        if location:
            meta_parts.append(location)
        meta = " • ".join(meta_parts)

        deadline_html = ""
        if deadline:
            deadline_html = f'<span style="color: #b45309; font-size: 13px;">Closes {format_date(deadline)}</span>'

        salary_html = ""
        if salary:
            salary_html = f'<p style="color: #1800ad; font-weight: 600; margin: 8px 0 0 0;">{salary}</p>'

        job_rows += f'''
        <tr>
          <td style="padding: 20px 0; border-bottom: 1px solid #e2ddd6;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <h3 style="margin: 0 0 6px 0; font-size: 17px; color: #1c1b19;">
                    <a href="{apply_url}" style="color: #1c1b19; text-decoration: none;">{title}</a>
                  </h3>
                  <p style="margin: 0 0 8px 0; color: #6d6760; font-size: 13px;">{meta}</p>
                  {deadline_html}
                  {salary_html}
                </td>
                <td width="100" align="right" valign="top">
                  <a href="{apply_url}" style="display: inline-block; background: #1800ad; color: white; padding: 10px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600;">View →</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        '''

    html = f'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JobberMed Weekly Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">

          <!-- Header -->
          <tr>
            <td style="padding: 0; background: #1800ad;">
              <img src="https://jobbermed.com/images/email-banner.jpg" alt=\"JobberMed banner\" width=\"600\" style=\"display:block;border:0;outline:none;text-decoration:none;width:100%;height:auto;\" />
            </td>
          </tr>

          <!-- Intro -->
          <tr>
            <td style="padding: 28px 40px 20px 40px;">
              <p style="margin: 0; color: #1c1b19; font-size: 15px; line-height: 1.6;">
                Here are the <strong>top {len(jobs)} medical and healthcare jobs</strong> posted this week across the healthcare industry in the country.
              </p>
            </td>
          </tr>

          <!-- Job Listings -->
          <tr>
            <td style="padding: 0 40px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {job_rows}
              </table>
            </td>
          </tr>

          <!-- CTA -->
          <tr>
            <td style="padding: 32px 40px; text-align: center;">
              <a href="https://jobbermed.com" style="display: inline-block; background: #1800ad; color: white; padding: 14px 32px; border-radius: 10px; text-decoration: none; font-size: 16px; font-weight: 600;">Browse All Jobs →</a>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background: #f5f6fb; padding: 24px 40px; text-align: center; border-top: 1px solid #e2ddd6;">
              <p style="margin: 0 0 8px 0; color: #6d6760; font-size: 13px;">
                You're receiving this because you subscribed at jobbermed.com
              </p>
              <p style="margin: 0; color: #6d6760; font-size: 13px;">
                <a href="{{{{unsubscribe}}}}" style="color: #1800ad;">Unsubscribe</a> · <a href="https://jobbermed.com" style="color: #1800ad;">Visit Website</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
'''
    return html


def send_campaign(html_content: str, job_count: int) -> bool:
    """Send email campaign via Brevo API."""

    api_key = os.getenv("BREVO_API_KEY")
    list_id = int(os.getenv("BREVO_LIST_ID", "0"))
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "jobs@jobbermed.com")
    sender_name = os.getenv("BREVO_SENDER_NAME", "JobberMed")

    if not api_key:
        print("❌ BREVO_API_KEY not set")
        return False

    if not list_id:
        print("❌ BREVO_LIST_ID not set")
        return False

    # Generate subject with date
    today = datetime.now()
    subject = f"{job_count} New Medical Jobs This Week — {today.strftime('%d %b %Y')}"

    # Create campaign
    campaign_url = "https://api.brevo.com/v3/emailCampaigns"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }

    campaign_data = {
        "name": f"Weekly Digest - {today.strftime('%Y-%m-%d')}",
        "subject": subject,
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "type": "classic",
        "htmlContent": html_content,
        "recipients": {
            "listIds": [list_id],
        },
        "scheduledAt": today.isoformat() + "Z",
    }

    try:
        print("📧 Creating email campaign...")
        response = requests.post(campaign_url, json=campaign_data, headers=headers)

        if response.status_code == 201:
            campaign_id = response.json().get("id")
            print(f"✅ Campaign created: ID {campaign_id}")

            send_url = f"https://api.brevo.com/v3/emailCampaigns/{campaign_id}/sendNow"
            send_response = requests.post(send_url, headers=headers)

            if send_response.status_code == 204:
                print("✅ Campaign sent successfully!")
                return True
            print(f"❌ Failed to send: {send_response.status_code}")
            print(send_response.text)
            return False

        print(f"❌ Failed to create campaign: {response.status_code}")
        print(response.text)
        return False

    except requests.RequestException as e:
        print(f"❌ API request failed: {e}")
        return False


def main() -> None:
    load_dotenv()

    print("=" * 60)
    print("  JOBBERMED WEEKLY NEWSLETTER")
    print("=" * 60)

    jobs_file = Path("docs/master_jobs.json")
    jobs = load_jobs(jobs_file, limit=20)
    print(f"\n📋 Loaded {len(jobs)} jobs")

    if len(jobs) == 0:
        print("⚠️  No jobs to send. Skipping newsletter.")
        return

    print("📝 Building email content...")
    html_content = build_email_html(jobs)

    preview_file = Path("docs/newsletter_preview.html")
    with open(preview_file, "w", encoding="utf-8") as f:
        f.write(html_content.replace("{{unsubscribe}}", "#"))
    print(f"📄 Preview saved: {preview_file}")

    if os.getenv("NEWSLETTER_DRY_RUN", "").lower() == "true":
        print("\n⏭️  Dry run mode — skipping send")
        return

    print("\n📤 Sending newsletter...")
    success = send_campaign(html_content, len(jobs))

    if success:
        print("\n" + "=" * 60)
        print("  ✅ NEWSLETTER SENT SUCCESSFULLY")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("  ❌ NEWSLETTER FAILED")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
