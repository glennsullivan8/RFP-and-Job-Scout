"""
generators/email_digest.py  —  Redesigned daily email digest
Clean top-10 lists, no auto-generated drafts.
Each card has a "Generate Application" link pointing to the dashboard.
"""

import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER     = os.getenv("GMAIL_USER", "glenn.sullivan8@gmail.com")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS", "")
TO_EMAIL       = "glenn.sullivan8@gmail.com"
DASHBOARD_URL  = os.getenv("DASHBOARD_URL", "https://glenn-sullivan-gisp.github.io/niche-management")

logger = logging.getLogger(__name__)

# ── Score color ────────────────────────────────────────────────────────────────

def _sc(score: int, max_s: int = 40) -> str:
    pct = score / max_s
    if pct >= 0.7: return "#0F6E56"
    if pct >= 0.45: return "#185FA5"
    if pct >= 0.25: return "#854F0B"
    return "#888780"

def _bar(score: int, max_s: int = 40) -> str:
    w = min(int(score / max_s * 100), 100)
    return f'<div style="background:#f0f0f0;border-radius:3px;height:5px;width:100%;margin-top:5px"><div style="background:{_sc(score,max_s)};height:5px;border-radius:3px;width:{w}%"></div></div>'

def _pills(kws: list) -> str:
    return " ".join(f'<span style="display:inline-block;background:#E1F5EE;color:#0F6E56;font-size:10px;padding:1px 7px;border-radius:10px;margin:1px">{k}</span>' for k in kws[:5])


# ── Card builders ──────────────────────────────────────────────────────────────

def _rfp_card(rfp: dict, rank: int) -> str:
    score = rfp.get("score", 0)
    color = _sc(score)
    local_badge = '<span style="background:#E6F1FB;color:#185FA5;font-size:10px;padding:1px 7px;border-radius:10px;margin-left:5px">📍 Local</span>' if rfp.get("is_local") else ""
    gen_url = f"{DASHBOARD_URL}?action=generate&id={rfp['id']}&type=rfp"
    hide_url = f"{DASHBOARD_URL}?action=hide&id={rfp['id']}"

    return f"""
<div style="background:white;border:1px solid #e8e8e8;border-radius:10px;padding:16px;margin-bottom:12px;border-left:4px solid {color}">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
    <div style="flex:1">
      <div style="font-size:11px;color:#999;margin-bottom:3px">#{rank} · {rfp.get('source','')}</div>
      <div style="font-size:15px;font-weight:600;color:#111;margin-bottom:3px">{rfp.get('title','')[:80]}{local_badge}</div>
      <div style="font-size:12px;color:#555;margin-bottom:6px">{rfp.get('org','')} {'· Deadline: ' + rfp.get('deadline','')[:10] if rfp.get('deadline') else ''} {'· Set-aside: ' + rfp.get('set_aside','') if rfp.get('set_aside') else ''}</div>
      <div style="font-size:12px;color:#333;line-height:1.5;margin-bottom:7px">{rfp.get('description','')[:200]}...</div>
      {_pills(rfp.get('matched_kws',[]))}
      {_bar(score)}
    </div>
    <div style="text-align:center;flex-shrink:0;min-width:44px">
      <div style="font-size:20px;font-weight:700;color:{color}">{score}</div>
      <div style="font-size:9px;color:#aaa">score</div>
    </div>
  </div>
  <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
    <a href="{rfp.get('url','#')}" style="display:inline-block;background:#0F6E56;color:white;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none">View RFP →</a>
    <a href="{gen_url}" style="display:inline-block;background:#185FA5;color:white;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none">Generate Application</a>
    <a href="{hide_url}" style="display:inline-block;background:#f5f5f5;color:#666;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none;border:1px solid #ddd">Not Interested</a>
  </div>
</div>"""


def _job_card(job: dict, rank: int) -> str:
    score = job.get("score", 0)
    color = _sc(score)
    type_colors = {
        "Federal": ("#E6F1FB", "#185FA5"),
        "PhD / Research": ("#FAECE7", "#993C1D"),
        "UAP Research": ("#EEEDFE", "#533AB7"),
        "Teaching": ("#E1F5EE", "#0F6E56"),
        "Fellowship": ("#FAEEDA", "#854F0B"),
    }
    bg, tc = type_colors.get(job.get("job_type",""), ("#F1EFE8","#5F5E5A"))
    gen_url = f"{DASHBOARD_URL}?action=generate&id={job['id']}&type=job"
    hide_url = f"{DASHBOARD_URL}?action=hide&id={job['id']}"
    remote_badge = '<span style="background:#E1F5EE;color:#0F6E56;font-size:10px;padding:1px 7px;border-radius:10px;margin-left:4px">Remote OK</span>' if job.get("remote") else ""

    return f"""
<div style="background:white;border:1px solid #e8e8e8;border-radius:10px;padding:16px;margin-bottom:12px;border-left:4px solid {color}">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
    <div style="flex:1">
      <div style="margin-bottom:5px">
        <span style="background:{bg};color:{tc};font-size:10px;padding:1px 8px;border-radius:10px;font-weight:500">#{rank} · {job.get('job_type','')}</span>
        {remote_badge}
      </div>
      <div style="font-size:15px;font-weight:600;color:#111;margin-bottom:2px">{job.get('title','')[:75]}</div>
      <div style="font-size:13px;font-weight:500;color:#444;margin-bottom:3px">{job.get('org','')}</div>
      <div style="font-size:12px;color:#666;margin-bottom:6px">{job.get('location','')} {'· ' + job.get('salary','') if job.get('salary') else ''}</div>
      <div style="font-size:12px;color:#333;line-height:1.5;margin-bottom:7px">{job.get('description','')[:180]}...</div>
      {_pills(job.get('matched_kws',[]))}
      {_bar(score)}
    </div>
    <div style="text-align:center;flex-shrink:0;min-width:44px">
      <div style="font-size:20px;font-weight:700;color:{color}">{score}</div>
      <div style="font-size:9px;color:#aaa">score</div>
    </div>
  </div>
  <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
    <a href="{job.get('url','#')}" style="display:inline-block;background:#185FA5;color:white;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none">View Job →</a>
    <a href="{gen_url}" style="display:inline-block;background:#0F6E56;color:white;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none">Generate Application</a>
    <a href="{hide_url}" style="display:inline-block;background:#f5f5f5;color:#666;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none;border:1px solid #ddd">Not Interested</a>
  </div>
</div>"""


def _mini_row(opp: dict, rank: int, opp_type: str) -> str:
    gen_url = f"{DASHBOARD_URL}?action=generate&id={opp['id']}&type={opp_type}"
    return f"""
<tr>
  <td style="padding:8px 10px;font-size:12px;color:#666;white-space:nowrap">#{rank}</td>
  <td style="padding:8px 10px;font-size:13px;color:#111">{opp.get('title','')[:60]}</td>
  <td style="padding:8px 10px;font-size:12px;color:#555">{opp.get('org','')[:30]}</td>
  <td style="padding:8px 10px;font-size:11px;color:#888">{opp.get('deadline','')[:10] or opp.get('posted','')[:10]}</td>
  <td style="padding:8px 10px;font-weight:600;font-size:13px;color:{_sc(opp.get('score',0))}">{opp.get('score',0)}</td>
  <td style="padding:8px 10px">
    <a href="{opp.get('url','#')}" style="color:#185FA5;font-size:11px;text-decoration:none">View</a> &nbsp;
    <a href="{gen_url}" style="color:#0F6E56;font-size:11px;text-decoration:none">Apply</a>
  </td>
</tr>"""


# ── Full HTML email ────────────────────────────────────────────────────────────

def build_html(rfps: list[dict], jobs: list[dict]) -> str:
    date_str   = datetime.now().strftime("%A, %B %d, %Y")
    top_rfps   = rfps[:10]
    top_jobs   = jobs[:10]
    local_rfps = [r for r in rfps if r.get("is_local") and r not in top_rfps][:15]
    rest_rfps  = [r for r in rfps[10:] if not r.get("is_local")][:30]
    rest_jobs  = jobs[10:40]

    rfp_cards = "".join(_rfp_card(r, i+1) for i, r in enumerate(top_rfps)) or "<p style='color:#888;font-style:italic'>No new RFPs matched today.</p>"
    job_cards = "".join(_job_card(j, i+1) for i, j in enumerate(top_jobs)) or "<p style='color:#888;font-style:italic'>No new job matches today.</p>"

    local_section = ""
    if local_rfps:
        local_rows = "".join(_mini_row(r, i+1, "rfp") for i, r in enumerate(local_rfps))
        local_section = f"""
        <div style="font-size:17px;font-weight:600;color:#111;margin:28px 0 4px">📍 Local / Roanoke Area RFPs</div>
        <div style="font-size:12px;color:#666;margin-bottom:12px">Within 120 miles of Salem, VA — drone-eligible opportunities</div>
        <table style="width:100%;border-collapse:collapse;background:white;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden">
          <thead><tr style="background:#E6F1FB">
            <th style="padding:8px 10px;font-size:11px;color:#185FA5;text-align:left">#</th>
            <th style="padding:8px 10px;font-size:11px;color:#185FA5;text-align:left">Opportunity</th>
            <th style="padding:8px 10px;font-size:11px;color:#185FA5;text-align:left">Agency</th>
            <th style="padding:8px 10px;font-size:11px;color:#185FA5;text-align:left">Deadline</th>
            <th style="padding:8px 10px;font-size:11px;color:#185FA5;text-align:left">Score</th>
            <th style="padding:8px 10px;font-size:11px;color:#185FA5;text-align:left">Links</th>
          </tr></thead>
          <tbody>{local_rows}</tbody>
        </table>"""

    rest_rfp_section = ""
    if rest_rfps:
        rows = "".join(_mini_row(r, i+1, "rfp") for i, r in enumerate(rest_rfps))
        rest_rfp_section = f"""
        <div style="font-size:15px;font-weight:600;color:#111;margin:28px 0 4px">All Other RFP Matches ({len(rest_rfps)} of {len(rfps)-10})</div>
        <table style="width:100%;border-collapse:collapse;background:white;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden">
          <thead><tr style="background:#F1EFE8">
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">#</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Opportunity</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Agency</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Posted/Deadline</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Score</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Links</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>"""

    rest_job_section = ""
    if rest_jobs:
        rows = "".join(_mini_row(j, i+1, "job") for i, j in enumerate(rest_jobs))
        rest_job_section = f"""
        <div style="font-size:15px;font-weight:600;color:#111;margin:28px 0 4px">All Other Job Matches ({len(rest_jobs)} of {len(jobs)-10})</div>
        <table style="width:100%;border-collapse:collapse;background:white;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden">
          <thead><tr style="background:#F1EFE8">
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">#</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Position</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Organization</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Deadline</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Score</th>
            <th style="padding:8px 10px;font-size:11px;color:#5F5E5A;text-align:left">Links</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f3;margin:0;padding:0">
<div style="max-width:700px;margin:0 auto;padding:20px 16px">

  <div style="background:#0F6E56;border-radius:12px;padding:22px;margin-bottom:18px;color:white">
    <div style="font-size:12px;opacity:0.75;margin-bottom:3px">Niche Management LLC · Daily Digest</div>
    <div style="font-size:22px;font-weight:600">Opportunity Report</div>
    <div style="font-size:13px;opacity:0.8;margin-bottom:14px">{date_str}</div>
    <div style="display:flex;gap:14px;flex-wrap:wrap">
      {''.join(f'<div style="background:rgba(255,255,255,0.15);border-radius:8px;padding:8px 14px;text-align:center"><div style="font-size:20px;font-weight:700">{v}</div><div style="font-size:10px;opacity:0.85">{l}</div></div>' for v, l in [(len(top_rfps),"Top RFPs"),(len(top_jobs),"Top Jobs"),(len(local_rfps),"Local RFPs"),(len(rfps)+len(jobs),"Total found")])}
    </div>
  </div>

  <div style="background:#FAEEDA;border-radius:8px;padding:10px 14px;margin-bottom:18px;font-size:12px;color:#5c3d0a">
    <strong>How to use:</strong> Review the top opportunities below. When you're ready to apply, click <strong>Generate Application</strong> — this opens the dashboard and creates a tailored Word document for you to review and send. Click <strong>Not Interested</strong> to permanently hide an opportunity from future digests.
  </div>

  <div style="font-size:18px;font-weight:600;color:#111;margin-bottom:4px">Top 10 RFP Opportunities</div>
  <div style="font-size:12px;color:#666;margin-bottom:14px">Ranked by relevance score · Filtered for your exact profile</div>
  {rfp_cards}

  <div style="font-size:18px;font-weight:600;color:#111;margin:28px 0 4px">Top 10 Job Opportunities</div>
  <div style="font-size:12px;color:#666;margin-bottom:14px">Federal, private, research, PhD & teaching positions</div>
  {job_cards}

  {local_section}
  {rest_rfp_section}
  {rest_job_section}

  <div style="text-align:center;margin-top:28px;padding-top:18px;border-top:1px solid #ddd">
    <a href="{DASHBOARD_URL}" style="display:inline-block;background:#0F6E56;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:13px;margin-bottom:14px">Open Full Dashboard</a>
    <div style="font-size:11px;color:#aaa">Glenn Sullivan, GISP · FAA Part 107 · Salem, VA · nichemanagementllc.com</div>
  </div>
</div></body></html>"""


# ── Send ───────────────────────────────────────────────────────────────────────

def send_digest(rfps: list[dict], jobs: list[dict]) -> bool:
    date_str = datetime.now().strftime("%b %d")
    subject  = f"🛰️ {len(rfps)} RFPs · {len(jobs)} Jobs · Niche Management Digest — {date_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL

    plain = f"Niche Management LLC — Daily Digest — {datetime.now().strftime('%A, %B %d, %Y')}\n\nTop {min(10,len(rfps))} RFPs and Top {min(10,len(jobs))} Jobs found. Open the dashboard at {DASHBOARD_URL} to view, generate applications, or mark not interested."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_html(rfps, jobs), "html"))

    if not GMAIL_APP_PASS:
        logger.warning("GMAIL_APP_PASS not set. Printing subject only.")
        print(subject)
        return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASS)
            s.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
        logger.info(f"✅ Digest sent to {TO_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False
