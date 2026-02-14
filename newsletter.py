#!/usr/bin/env python3
"""Send weekly job digest newsletter via Brevo"""

import json
import os
import sys
from datetime import datetime
from html import escape
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
    invalid_salary_values = {"", "n", "n,", "na", "n/a", "none", "null", "-", "--", "nil"}

    # Build job cards in a monochrome-forward style with subtle brand accents.
    job_rows = ""
    for job in jobs:
        title = escape(str(job.get("job_title") or "Untitled Role"))
        company = escape(str(job.get("company") or "Company not listed"))
        location = escape(str(job.get("location") or "").strip())
        apply_url = escape(str(job.get("apply_url") or "https://jobbermed.com"), quote=True)

        salary_raw = str(job.get("salary") or "").strip()
        salary_normalized = salary_raw.lower()

        posted_raw = str(job.get("date_posted") or "").strip()
        deadline_raw = str(job.get("deadline") or "").strip()
        job_type_raw = str(job.get("job_type") or "").strip()

        meta = company
        if location:
            meta = f"{meta} • {location}"

        tags = []
        if posted_raw:
            tags.append(
                f'<span style="display:inline-block;background:#f0f0f0;color:#111111;'
                f'font-size:12px;line-height:1;padding:6px 10px;border-radius:999px;'
                f'margin-right:6px;margin-bottom:6px;">Posted {escape(format_date(posted_raw))}</span>'
            )
        if deadline_raw:
            tags.append(
                f'<span style="display:inline-block;background:#f0f0f0;color:#111111;'
                f'font-size:12px;line-height:1;padding:6px 10px;border-radius:999px;'
                f'margin-right:6px;margin-bottom:6px;">Closes {escape(format_date(deadline_raw))}</span>'
            )
        if job_type_raw:
            tags.append(
                f'<span style="display:inline-block;background:#f0f0f0;color:#111111;'
                f'font-size:12px;line-height:1;padding:6px 10px;border-radius:999px;'
                f'margin-right:6px;margin-bottom:6px;">{escape(job_type_raw)}</span>'
            )
        tags_html = f'<p style="margin:0 0 10px 0;">{"".join(tags)}</p>' if tags else ""

        salary_html = ""
        if salary_normalized not in invalid_salary_values:
            salary_html = (
                f'<p style="margin:0; color:#1800ad; font-weight:600; font-size:13px;">'
                f"{escape(salary_raw)}"
                "</p>"
            )

        job_rows += f"""
        <tr>
          <td style="padding: 0 32px 14px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2ddd6; border-radius:16px; background:#ffffff;">
              <tr>
                <td style="padding: 16px 18px 10px 18px;">
                  <h3 style="margin: 0 0 8px 0; font-size: 18px; line-height: 1.35; color: #1c1b19; font-weight: 600;">
                    <a href="{apply_url}" style="color:#1c1b19; text-decoration:none;">{title}</a>
                  </h3>
                  <p style="margin: 0 0 10px 0; color: #6d6760; font-size: 13px; line-height: 1.4;">{meta}</p>
                  {tags_html}
                  {salary_html}
                </td>
              </tr>
              <tr>
                <td style="padding: 0 18px 16px 18px;">
                  <a href="{apply_url}" style="display:inline-block; background:#111111; color:#ffffff; padding:10px 16px; border-radius:10px; text-decoration:none; font-size:13px; font-weight:600;">
                    View Original Posting →
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JobberMed Weekly Digest</title>
</head>
<body style="margin:0; padding:0; background-color:#f7f4ef; font-family:'IBM Plex Sans','Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f4ef; padding:28px 12px;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="width:100%; max-width:640px; background-color:#ffffff; border-radius:18px; overflow:hidden; border:1px solid #e2ddd6; box-shadow:0 10px 24px rgba(0,0,0,0.06);">
          <tr>
            <td style="height:12px; line-height:12px; font-size:0; background:#1800ad; background-image:linear-gradient(90deg,#1800ad 0%,#0cc0df 100%);">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding:26px 32px; background:#111111;">
              <h1 style="margin:0; color:#ffffff; font-size:28px; line-height:1.2; font-weight:800;">
                Healthcare jobs across Nigeria and Africa.
              </h1>
              <div style="width:180px; height:5px; margin-top:14px; border-radius:999px; background:#0cc0df;"></div>
              <p style="margin:14px 0 0 0; color:rgba(255,255,255,0.85); font-size:15px; line-height:1.5;">
                Delivered to your email every week.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 20px 32px;">
              <p style="margin:0; color:#1c1b19; font-size:15px; line-height:1.6;">
                Here are the top <strong>{len(jobs)} medical and healthcare opportunities</strong> curated this week.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {job_rows}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 34px 32px; text-align:center;">
              <a href="https://jobbermed.com" style="display:inline-block; background:#111111; color:#ffffff; padding:14px 32px; border-radius:12px; text-decoration:none; font-size:16px; font-weight:600;">
                Browse All Jobs →
              </a>
            </td>
          </tr>
          <tr>
            <td style="background:#111111; padding:24px 32px; text-align:center;">
              <p style="margin:0 0 8px 0; color:rgba(255,255,255,0.72); font-size:13px; line-height:1.5;">
                You're receiving this because you subscribed at jobbermed.com
              </p>
              <p style="margin:0; color:rgba(255,255,255,0.72); font-size:13px;">
                <a href="{{{{unsubscribe}}}}" style="color:#0cc0df; text-decoration:none;">Unsubscribe</a> · <a href="https://jobbermed.com" style="color:#0cc0df; text-decoration:none;">Visit Website</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html_content


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
