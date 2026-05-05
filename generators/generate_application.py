"""
generators/generate_application.py
Called when Glenn clicks "Generate Application" on the dashboard.
1. Calls Claude API to write tailored draft content
2. Passes draft to make_doc.js to produce a .docx
3. Saves the file and marks opportunity as "applied" in tracker
"""

import os
import sys
import json
import subprocess
import logging
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tracker import mark_applied, set_status

logger = logging.getLogger(__name__)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL  = "claude-sonnet-4-20250514"
DOCS_DIR      = Path(os.getenv("DOCS_DIR", "generated_docs"))

PROFILE_SUMMARY = """
Glenn Sullivan, GISP — Niche Management LLC
13+ years GIS & remote sensing consultant.
Awards: 2024 USDA Secretary's Honor Award, 2023 USFS Chief's Honor Award.
NASA project history: harmful algae bloom LiDAR mapping (MTRI), food security satellite app.
Skills: Python, ArcPy, FME, ArcGIS Online/Enterprise, ArcGIS JS SDK, React, PostgreSQL, Django.
Remote sensing: NDVI from Landsat, LiDAR via PDAL, object detection, GeoAI, DLPKs.
Drone: FAA Part 107 licensed, Drone2Map, ArcGIS Flight, photogrammetry, DEM.
Emergency response: Camp Fire, Thomas Fire, Husky Refinery, EPA Superfund.
Federal clients: NASA, USFS, EPA, FEMA, NOAA, USGS, MDOT.
GISP #161655 | FAA Part 107 | 6 ESRI Technical Certifications.
"""


def _call_claude(prompt: str) -> str:
    if not ANTHROPIC_KEY:
        return ""
    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1500,
        "system": f"You are a professional proposal writer and career advisor for {PROFILE_SUMMARY}. Be specific, compelling, and concise. Never use generic language.",
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Claude API: {e}")
        return ""


def _parse_json_response(text: str, fallback: dict) -> dict:
    """Extract JSON from Claude response."""
    try:
        # Try to find JSON block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return fallback


# ── RFP proposal draft ─────────────────────────────────────────────────────────

def draft_rfp_content(rfp: dict) -> dict:
    """Call Claude to generate RFP proposal content. Returns structured dict."""
    prompt = f"""Write a tailored federal RFP proposal for Glenn Sullivan / Niche Management LLC.

RFP DETAILS:
Title: {rfp.get('title', '')}
Agency: {rfp.get('org', '')}
Description: {rfp.get('description', '')}
Keywords matched: {', '.join(rfp.get('matched_kws', []))}
Set-aside: {rfp.get('set_aside', '')}

Respond ONLY with a JSON object (no markdown, no explanation) with these keys:
{{
  "executive_summary": ["paragraph 1", "paragraph 2"],
  "technical_approach": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "relevant_experience": ["paragraph about most relevant past project", "paragraph about second most relevant"],
  "why_us": ["compelling closing paragraph"]
}}

Make every sentence specific to this RFP. Reference Glenn's NASA experience, USFS awards, and exact skills matching this opportunity."""

    if ANTHROPIC_KEY:
        raw = _call_claude(prompt)
        return _parse_json_response(raw, _rfp_fallback(rfp))
    return _rfp_fallback(rfp)


def _rfp_fallback(rfp: dict) -> dict:
    """Fallback draft when API key not set."""
    kws = ", ".join(rfp.get("matched_kws", [])[:4])
    return {
        "executive_summary": [
            f"Niche Management LLC, led by Glenn Sullivan, GISP, is exceptionally qualified to support {rfp.get('org', 'your agency')} with this {rfp.get('title', 'opportunity')}. With 13+ years of federal GIS and remote sensing experience spanning NASA, USFS, EPA, FEMA, and NOAA, Glenn brings a rare combination of technical depth and proven federal delivery capability.",
            f"Glenn is the recipient of the 2024 USDA Secretary's Honor Award — one of the highest honors in federal service — for critical technical contributions to national climate resilience. His expertise in {kws} directly addresses the core requirements of this solicitation.",
        ],
        "technical_approach": [
            "Conduct thorough requirements analysis and develop a tailored technical methodology",
            f"Apply proven expertise in {kws} to deliver high-quality geospatial products",
            "Utilize Python automation, ArcPy, and FME workflows to ensure efficient, repeatable processes",
            "Provide comprehensive documentation, quality control, and client communication throughout",
            "Deliver on-time, on-budget results consistent with 13+ years of federal project success",
        ],
        "relevant_experience": [
            "As Lead GIS Developer for the USFS Climate Risk Viewer, Glenn designed and delivered a complex multi-application geospatial platform (11 StoryMaps, 10 Experience Builders, 140+ data layers) recognized with the 2024 USDA Secretary's Honor Award and 2023 USFS Chief's Honor Award.",
            "At Michigan Tech Research Institute, Glenn supported two NASA contracts including harmful algae bloom satellite mapping using MODIS Aqua imagery and LiDAR flyover data for Lake Erie, demonstrating direct expertise in satellite remote sensing and data processing pipelines.",
        ],
        "why_us": [
            "Niche Management LLC offers the rare combination of a sole-practitioner's agility and accountability with the credentials and federal track record of a seasoned senior GIS engineer. Glenn Sullivan's GISP certification, FAA Part 107 drone license, six ESRI technical certifications, and two USFS Honor Awards represent a uniquely qualified resource for this opportunity. We will deliver.",
        ],
    }


# ── Job application draft ──────────────────────────────────────────────────────

def draft_job_content(job: dict) -> dict:
    """Call Claude to generate cover letter and resume summary."""
    prompt = f"""Write tailored job application content for Glenn Sullivan applying to this role.

JOB:
Title: {job.get('title', '')}
Organization: {job.get('org', '')}
Description: {job.get('description', '')}
Type: {job.get('job_type', '')}
Skills matched: {', '.join(job.get('matched_kws', []))}

Respond ONLY with a JSON object (no markdown, no explanation):
{{
  "cover_letter": ["opening paragraph", "second paragraph highlighting specific experience", "third paragraph with passion/mission alignment", "closing paragraph"],
  "resume_summary": "3-4 sentence professional summary tailored to this exact role, ATS-optimized, under 80 words"
}}

The cover letter must be warm, specific, and convey genuine passion. Reference Glenn's NASA experience and USFS awards where relevant. Never use generic phrases like 'I am writing to express my interest'."""

    if ANTHROPIC_KEY:
        raw = _call_claude(prompt)
        return _parse_json_response(raw, _job_fallback(job))
    return _job_fallback(job)


def _job_fallback(job: dict) -> dict:
    org = job.get("org", "your organization")
    title = job.get("title", "this role")
    return {
        "cover_letter": [
            f"The opportunity to contribute to {org}'s work in remote sensing and geospatial intelligence is something I've been working toward throughout my 13-year career. This role aligns precisely with what I do best and what I'm most passionate about.",
            "As the Lead GIS Developer for the USFS Climate Risk Viewer — a national-scale geospatial platform that earned me the 2024 USDA Secretary's Honor Award — I've demonstrated the ability to deliver complex remote sensing and GIS solutions to demanding federal clients. My earlier work at Michigan Tech Research Institute on two NASA contracts, including satellite-based harmful algae bloom mapping using MODIS and LiDAR data, gave me a foundation in exactly the kind of sensor-to-insight workflows this role demands.",
            f"What draws me most to {org} is the mission. I genuinely believe that remote sensing technology, applied thoughtfully, can solve problems that matter — from climate resilience to environmental monitoring to understanding phenomena we don't yet fully comprehend. I want to spend my career on work like that.",
            f"I'd welcome the chance to discuss how my background in GIS, LiDAR, Python automation, drone operations, and federal emergency response might serve {org}'s goals. Thank you for your consideration.",
        ],
        "resume_summary": f"Award-winning GIS and remote sensing consultant with 13+ years delivering geospatial solutions to NASA, USFS, EPA, FEMA, and NOAA. GISP certified, FAA Part 107 licensed, and 2024 USDA Secretary's Honor Award recipient. Expertise in satellite/LiDAR remote sensing, GeoAI, Python/ArcPy automation, and ArcGIS platform development. Seeking to apply proven federal project experience to {title}.",
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────

def generate_application(opp: dict) -> Path:
    """
    Full pipeline: draft → docx → save.
    Returns path to generated .docx file.
    """
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    opp_type = opp.get("type", "rfp")
    date_str = datetime.now().strftime("%Y%m%d")
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in opp.get("title", "doc")[:40])
    out_path = DOCS_DIR / f"{date_str}_{opp_type}_{safe_title}.docx"

    logger.info(f"Generating {opp_type} doc: {out_path.name}")
    set_status(opp["id"], "generating")

    # 1. Get Claude draft
    if opp_type == "rfp":
        draft = draft_rfp_content(opp)
    else:
        draft = draft_job_content(opp)

    # 2. Write data JSON for JS doc maker
    data_path = DOCS_DIR / "_tmp_data.json"
    doc_key = "rfp" if opp_type == "rfp" else "job"
    data_path.write_text(json.dumps({doc_key: opp, "draft": draft}, indent=2))

    # 3. Call Node.js doc maker
    js_path = Path(__file__).parent / "make_doc.js"
    result = subprocess.run(
        ["node", str(js_path), opp_type, str(data_path), str(out_path)],
        capture_output=True, text=True
    )
    data_path.unlink(missing_ok=True)

    if result.returncode != 0:
        logger.error(f"make_doc.js failed: {result.stderr}")
        set_status(opp["id"], "seen")
        raise RuntimeError(f"Document generation failed: {result.stderr[:200]}")

    logger.info(f"Document created: {out_path}")
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Test with a mock opportunity
    mock = {
        "id": "test-001", "type": "rfp",
        "title": "Remote Sensing and GIS Support for USFS Climate Analysis",
        "org": "US Forest Service", "source": "SAM.gov",
        "posted": "2026-05-01", "deadline": "2026-06-01",
        "description": "Seeking GIS and remote sensing contractor for LiDAR processing, NDVI analysis, and web app development.",
        "matched_kws": ["remote sensing", "LiDAR", "NDVI", "ArcGIS", "GIS"],
        "set_aside": "Small Business", "naics": "541370", "url": "https://sam.gov",
    }
    path = generate_application(mock)
    print(f"Generated: {path}")
