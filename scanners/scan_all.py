"""
scanners/scan_all.py  —  Unified scanner for RFPs and jobs
Returns two lists: rfps, jobs — each sorted by score, filtered for relevance,
with hidden opportunities removed.
"""

import os
import re
import math
import json
import logging
import hashlib
import requests
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from filters import is_relevant, passion_boost
from tracker import filter_opportunities, mark_all_seen

logger = logging.getLogger(__name__)

SAM_API_KEY     = os.getenv("SAM_API_KEY", "")
USAJOBS_API_KEY = os.getenv("USAJOBS_API_KEY", "")
USAJOBS_EMAIL   = "glenn.sullivan8@gmail.com"
DAYS_BACK       = int(os.getenv("DAYS_BACK", "3"))
MAX_TOTAL       = 50   # hard cap on total results per category

# Roanoke VA coords for geo-filter
ROANOKE = (37.2710, -79.9414)
MAX_DRONE_MILES = 120


# ── Scoring ────────────────────────────────────────────────────────────────────

SCORE_WEIGHTS = {
    "remote sensing": 6, "lidar": 6, "satellite imagery": 6,
    "object detection": 6, "object tracking": 5, "object classification": 5,
    "geoai": 6, "geospatial ai": 6, "pixel classification": 5,
    "drone": 5, "uas": 5, "suas": 5, "aerial survey": 5, "photogrammetry": 5,
    "gis": 4, "geospatial": 4, "arcgis": 4, "arcpy": 5,
    "python": 3, "fme": 4, "lidar": 5, "ndvi": 5,
    "nasa": 5, "noaa": 4, "usgs": 4, "usfs": 4,
    "astronomy": 4, "space": 3, "uap": 5, "anomalous": 5,
    "environmental monitoring": 3, "vegetation analysis": 4, "climate": 3,
    "geospatial developer": 5, "gis developer": 5,
    "research scientist": 4, "phd": 3, "fellowship": 3,
    "machine learning": 3, "deep learning": 3, "computer vision": 4,
    "imagery analyst": 4, "geoint": 5, "nga": 4,
}

DREAM_ORG_BOOST = {
    "nasa": 8, "jpl": 8, "jet propulsion": 8,
    "galileo project": 8, "sol foundation": 7,
    "seti": 7, "noaa": 5, "usgs": 4, "usfs": 4,
    "lockheed": 5, "raytheon": 5, "leidos": 4,
    "boeing": 4, "maxar": 5, "radiance": 4,
    "planet labs": 5, "esri": 4,
    "space force": 5, "bigelow": 4,
    "nga": 5, "dia": 4, "nro": 4,
    "virginia tech": 5, "vt": 3,
}


def _score(title: str, description: str, org: str = "") -> tuple[int, list[str]]:
    text = f"{title} {description}".lower()
    matched, score = [], 0
    seen = set()
    for kw, pts in SCORE_WEIGHTS.items():
        if kw in text and kw not in seen:
            matched.append(kw)
            score += pts
            seen.add(kw)
    for org_kw, pts in DREAM_ORG_BOOST.items():
        if org_kw in f"{org} {text}".lower():
            score += pts
            break
    score += passion_boost(title, description)
    return min(score, 40), matched[:10]


def _make_id(source: str, title: str, raw_id: str = "") -> str:
    if raw_id:
        return f"{source.lower()[:6]}-{raw_id}"
    h = hashlib.md5(f"{source}{title}".encode()).hexdigest()[:10]
    return f"{source.lower()[:6]}-{h}"


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


VA_COUNTIES_NEAR = [
    "roanoke", "salem", "bedford", "botetourt", "montgomery", "franklin",
    "floyd", "pulaski", "rockbridge", "augusta", "alleghany", "craig", "giles",
]


def _in_drone_range(notice: dict) -> bool:
    pop = notice.get("placeOfPerformance", {})
    state = (pop.get("state", {}).get("code") or "").upper()
    county = (pop.get("county", "") or "").lower()
    if not state:
        return True  # unknown — include for manual review
    near_states = {"VA", "WV", "TN", "NC", "KY", "MD"}
    if state not in near_states:
        return False
    if state == "VA":
        return not county or any(c in county for c in VA_COUNTIES_NEAR)
    return True


# ── SAM.gov ────────────────────────────────────────────────────────────────────

def _scan_sam() -> list[dict]:
    results = []
    posted_from = (datetime.utcnow() - timedelta(days=DAYS_BACK)).strftime("%m/%d/%Y")
    posted_to   = datetime.utcnow().strftime("%m/%d/%Y")
    searches = [
        "remote sensing GIS geospatial LiDAR",
        "drone UAS sUAS unmanned aerial survey",
        "object detection GeoAI satellite imagery",
        "environmental monitoring vegetation NASA USGS",
        "geospatial developer ArcGIS python",
    ]
    headers = {"X-Api-Key": SAM_API_KEY} if SAM_API_KEY else {}
    for kw in searches:
        params = {
            "limit": 50, "postedFrom": posted_from, "postedTo": posted_to,
            "ptype": "o,p,k,r,s", "keyword": kw, "active": "true",
        }
        if SAM_API_KEY:
            params["api_key"] = SAM_API_KEY
        try:
            r = requests.get("https://api.sam.gov/opportunities/v2/search",
                             params=params, headers=headers, timeout=30)
            r.raise_for_status()
            for hit in r.json().get("opportunitiesData", []):
                title = hit.get("title", "")
                desc  = hit.get("description", "")
                ok, reason = is_relevant(title, desc, "SAM.gov")
                if not ok:
                    continue
                score, matched = _score(title, desc, hit.get("department", ""))
                is_drone = any(t in matched for t in ["drone", "uas", "suas", "aerial survey"])
                if is_drone and not _in_drone_range(hit):
                    continue
                opp_id = _make_id("sam", title, hit.get("noticeId", ""))
                results.append({
                    "id": opp_id, "type": "rfp", "source": "SAM.gov",
                    "title": title, "org": hit.get("department", ""),
                    "posted": hit.get("postedDate", "")[:10],
                    "deadline": hit.get("responseDeadLine", "")[:10],
                    "description": desc[:400], "score": score,
                    "matched_kws": matched,
                    "url": f"https://sam.gov/opp/{hit.get('noticeId','')}/view",
                    "set_aside": hit.get("typeOfSetAside", ""),
                    "naics": hit.get("naicsCode", ""),
                    "is_local": is_drone,
                    "is_drone": is_drone,
                })
        except Exception as e:
            logger.warning(f"SAM '{kw}': {e}")
    return results


# ── SBIR ───────────────────────────────────────────────────────────────────────

def _scan_sbir() -> list[dict]:
    results = []
    try:
        r = requests.get(
            "https://api.sbir.gov/public/api/solicitations?agency=NASA,NOAA,DOD,NSF,EPA&open=1",
            timeout=30)
        r.raise_for_status()
        for item in (r.json() if isinstance(r.json(), list) else []):
            title = item.get("program_title", "") or item.get("title", "")
            desc  = item.get("program_description", "") or ""
            ok, _ = is_relevant(title, desc, "SBIR")
            if not ok:
                continue
            score, matched = _score(title, desc, item.get("agency", ""))
            results.append({
                "id": _make_id("sbir", title, str(item.get("solicitation_id", ""))),
                "type": "rfp", "source": "SBIR.gov",
                "title": title, "org": item.get("agency", ""),
                "posted": item.get("open_date", "")[:10],
                "deadline": item.get("close_date", "")[:10],
                "description": desc[:400], "score": score,
                "matched_kws": matched,
                "url": item.get("solicitation_url", "https://www.sbir.gov/"),
                "set_aside": "SBIR/STTR Small Business", "naics": "",
                "is_local": False, "is_drone": False,
            })
    except Exception as e:
        logger.warning(f"SBIR: {e}")
    return results


# ── Virginia eVA ───────────────────────────────────────────────────────────────

def _scan_eva() -> list[dict]:
    results = []
    try:
        r = requests.get(
            "https://eva.virginia.gov/pages/eprocurement-open-bids.html", timeout=30)
        r.raise_for_status()
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL | re.IGNORECASE)
        for row in rows:
            text = re.sub(r'<[^>]+>', ' ', row)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) < 20:
                continue
            ok, _ = is_relevant(text, text, "eVA")
            if not ok:
                continue
            score, matched = _score(text, text, "Virginia")
            results.append({
                "id": _make_id("eva", text),
                "type": "rfp", "source": "Virginia eVA",
                "title": text[:100], "org": "Virginia State / Local",
                "posted": datetime.utcnow().strftime("%Y-%m-%d"), "deadline": "See eVA portal",
                "description": text[:300], "score": score,
                "matched_kws": matched,
                "url": "https://eva.virginia.gov/pages/eprocurement-open-bids.html",
                "set_aside": "Virginia SWaM", "naics": "",
                "is_local": True, "is_drone": "drone" in " ".join(matched).lower(),
            })
    except Exception as e:
        logger.warning(f"eVA: {e}")
    return results


# ── USAJobs ────────────────────────────────────────────────────────────────────

def _scan_usajobs() -> list[dict]:
    if not USAJOBS_API_KEY:
        logger.warning("No USAJOBS_API_KEY — using curated links")
        return _usajobs_curated()
    results = []
    headers = {
        "Authorization-Key": USAJOBS_API_KEY,
        "User-Agent": USAJOBS_EMAIL,
        "Host": "data.usajobs.gov",
    }
    searches = [
        "remote sensing GIS geospatial",
        "LiDAR satellite imagery analyst",
        "drone UAS geospatial analyst",
        "GeoAI machine learning geospatial",
        "geospatial intelligence GEOINT",
        "remote sensing research scientist",
    ]
    for kw in searches:
        try:
            r = requests.get(
                "https://data.usajobs.gov/api/search",
                headers=headers,
                params={"Keyword": kw, "ResultsPerPage": 25, "DatePosted": DAYS_BACK},
                timeout=30)
            r.raise_for_status()
            for hit in r.json().get("SearchResult", {}).get("SearchResultItems", []):
                pos   = hit.get("MatchedObjectDescriptor", {})
                title = pos.get("PositionTitle", "")
                org   = pos.get("OrganizationName", "")
                desc  = pos.get("QualificationSummary", "")
                ok, _ = is_relevant(title, desc, org)
                if not ok:
                    continue
                score, matched = _score(title, desc, org)
                sal = pos.get("PositionRemuneration", [{}])
                sal_str = f"${sal[0].get('MinimumRange','?')}–${sal[0].get('MaximumRange','?')}" if sal else ""
                results.append({
                    "id": _make_id("usa", title, pos.get("PositionID", "")),
                    "type": "job", "source": "USAJobs",
                    "title": title, "org": org,
                    "posted": pos.get("PublicationStartDate", "")[:10],
                    "deadline": pos.get("ApplicationCloseDate", "")[:10],
                    "description": desc[:400], "score": score,
                    "matched_kws": matched,
                    "url": pos.get("PositionURI", ""),
                    "salary": sal_str,
                    "location": pos.get("PositionLocationDisplay", ""),
                    "remote": "remote" in pos.get("PositionLocationDisplay", "").lower(),
                    "job_type": "Federal",
                })
        except Exception as e:
            logger.warning(f"USAJobs '{kw}': {e}")
    return results


def _usajobs_curated() -> list[dict]:
    """Curated high-priority federal links when API key not set."""
    return [
        {"id": "usa-nasa-rs", "type": "job", "source": "USAJobs", "title": "Remote Sensing / GIS Positions — NASA",
         "org": "NASA", "posted": "", "deadline": "Ongoing", "description": "Search NASA remote sensing and GIS positions on USAJobs.",
         "score": 18, "matched_kws": ["nasa", "remote sensing", "gis"],
         "url": "https://www.usajobs.gov/Search/Results?k=remote+sensing+GIS&d=NN",
         "salary": "GS-11–GS-15 (~$73k–$159k)", "location": "Various / Remote", "remote": True, "job_type": "Federal"},
        {"id": "usa-noaa-rs", "type": "job", "source": "USAJobs", "title": "Remote Sensing / Satellite Analyst — NOAA",
         "org": "NOAA", "posted": "", "deadline": "Ongoing", "description": "NOAA remote sensing, satellite, and environmental monitoring roles.",
         "score": 15, "matched_kws": ["noaa", "satellite imagery", "remote sensing"],
         "url": "https://www.usajobs.gov/Search/Results?k=remote+sensing+GIS&d=CM",
         "salary": "GS-11–GS-14", "location": "Various", "remote": True, "job_type": "Federal"},
        {"id": "usa-nga-geo", "type": "job", "source": "USAJobs", "title": "GEOINT / Imagery Analyst — NGA / DIA",
         "org": "NGA / DIA", "posted": "", "deadline": "Ongoing", "description": "Geospatial intelligence and imagery analysis roles.",
         "score": 16, "matched_kws": ["geoint", "nga", "imagery analyst", "remote sensing"],
         "url": "https://www.usajobs.gov/Search/Results?k=geospatial+intelligence+imagery",
         "salary": "GS-11–GS-14", "location": "Various", "remote": False, "job_type": "Federal"},
    ]


# ── Private companies ──────────────────────────────────────────────────────────

PRIVATE_JOBS = [
    {"name": "Leidos", "score_base": 12, "url": "https://careers.leidos.com/search/remote+sensing+GIS/jobs",
     "kws": ["remote sensing", "gis", "geospatial", "geoint"], "type": "Defense / Intel"},
    {"name": "Maxar Technologies", "score_base": 14, "url": "https://maxar.wd1.myworkdayjobs.com/maxar/jobs",
     "kws": ["satellite imagery", "remote sensing", "object detection", "geoai"], "type": "Space / Geospatial"},
    {"name": "Planet Labs", "score_base": 13, "url": "https://www.planet.com/company/careers/",
     "kws": ["satellite imagery", "remote sensing", "gis", "geospatial"], "type": "Space / Geospatial"},
    {"name": "Lockheed Martin", "score_base": 12, "url": "https://www.lockheedmartinjobs.com/search-jobs/remote%20sensing%20GIS/694/1",
     "kws": ["remote sensing", "gis", "geospatial", "lidar"], "type": "Defense / Aerospace"},
    {"name": "Raytheon Technologies", "score_base": 12, "url": "https://careers.rtx.com/global/en/search-results?keywords=remote+sensing+GIS",
     "kws": ["remote sensing", "sensor", "imagery", "geospatial"], "type": "Defense / Aerospace"},
    {"name": "Radiance Technologies", "score_base": 11, "url": "https://www.radiancetech.com/careers/",
     "kws": ["remote sensing", "gis", "geospatial"], "type": "Defense"},
    {"name": "Boeing", "score_base": 11, "url": "https://jobs.boeing.com/search-jobs/remote%20sensing%20GIS/185/1",
     "kws": ["remote sensing", "satellite", "gis"], "type": "Aerospace"},
    {"name": "Esri", "score_base": 13, "url": "https://www.esri.com/en-us/about/careers/job-search",
     "kws": ["gis developer", "arcgis", "remote sensing", "geospatial"], "type": "GIS Technology"},
]

RESEARCH_JOBS = [
    {"name": "The Galileo Project (Harvard)", "score_base": 18,
     "url": "https://projects.iq.harvard.edu/galileo/join-us",
     "kws": ["remote sensing", "uap", "anomalous", "sensor", "research"], "type": "UAP Research"},
    {"name": "SETI Institute", "score_base": 15, "url": "https://www.seti.org/about-us/careers",
     "kws": ["astronomy", "research", "data science", "signal analysis"], "type": "Space Research"},
    {"name": "Sol Foundation", "score_base": 14, "url": "https://thesolfoundation.org",
     "kws": ["uap", "research", "remote sensing"], "type": "UAP Research"},
    {"name": "NASA JPL", "score_base": 20, "url": "https://www.jpl.nasa.gov/edu/intern/apply/",
     "kws": ["remote sensing", "lidar", "satellite", "space"], "type": "Space Research"},
    {"name": "MUFON / AIAA UAP", "score_base": 10, "url": "https://www.mufon.com",
     "kws": ["uap", "research", "sensor"], "type": "UAP Research"},
    {"name": "Bigelow Aerospace", "score_base": 10, "url": "https://bigelowaerospace.com",
     "kws": ["space", "aerospace", "sensor"], "type": "Commercial Space"},
]

VT_TARGETS = [
    {"name": "Virginia Tech — PhD / Research Assistant", "score_base": 16,
     "url": "https://geography.vt.edu/graduate.html",
     "kws": ["remote sensing", "gis", "geospatial", "phd", "research"], "type": "PhD / Research"},
    {"name": "Virginia Tech — Adjunct / Lecturer (GIS or Remote Sensing)", "score_base": 15,
     "url": "https://careers.vt.edu", "kws": ["gis", "remote sensing", "teaching"], "type": "Teaching"},
    {"name": "VT Transportation Research Council — Drone & GIS Contracts", "score_base": 14,
     "url": "https://vtrc.vt.edu/", "kws": ["drone", "gis", "remote sensing", "survey"], "type": "Research Contract"},
    {"name": "VT-NASA Joint Research Proposal", "score_base": 13,
     "url": "https://research.vt.edu/", "kws": ["nasa", "research", "remote sensing"], "type": "Funding / Collaboration"},
    {"name": "NASA FINESST Fellowship (via VT)", "score_base": 17,
     "url": "https://science.nasa.gov/researchers/solicitations/roses-2024/",
     "kws": ["nasa", "fellowship", "research", "remote sensing"], "type": "Fellowship"},
]


def _build_private_jobs() -> list[dict]:
    jobs = []
    for co in PRIVATE_JOBS + RESEARCH_JOBS + VT_TARGETS:
        jobs.append({
            "id": _make_id("prv", co["name"]),
            "type": "job", "source": co.get("type", "Private"),
            "title": f"Remote Sensing / GIS Roles — {co['name']}",
            "org": co["name"], "posted": "", "deadline": "Ongoing",
            "description": f"Search for {', '.join(co['kws'][:3])} positions at {co['name']}.",
            "score": co["score_base"],
            "matched_kws": co["kws"],
            "url": co["url"],
            "salary": "Competitive / Stipend",
            "location": "Various", "remote": True,
            "job_type": co.get("type", "Private"),
        })
    return jobs


# ── Main entry ─────────────────────────────────────────────────────────────────

def run_all_scans() -> tuple[list[dict], list[dict]]:
    """
    Returns (rfps, jobs) — each filtered, deduplicated, sorted by score.
    Hidden opportunities are removed. All remaining are marked as seen.
    """
    logger.info("Starting full scan...")

    # Gather
    raw_rfps = _scan_sam() + _scan_sbir() + _scan_eva()
    raw_jobs = _scan_usajobs() + _build_private_jobs()

    # Deduplicate
    rfps = _dedup(raw_rfps)
    jobs = _dedup(raw_jobs)

    # Remove hidden
    rfps = filter_opportunities(rfps)
    jobs = filter_opportunities(jobs)

    # Sort
    rfps.sort(key=lambda x: x["score"], reverse=True)
    jobs.sort(key=lambda x: x["score"], reverse=True)

    # Cap
    rfps = rfps[:MAX_TOTAL]
    jobs = jobs[:MAX_TOTAL]

    # Mark seen
    mark_all_seen(rfps, "rfp")
    mark_all_seen(jobs, "job")

    logger.info(f"Results: {len(rfps)} RFPs, {len(jobs)} jobs")
    return rfps, jobs


def _dedup(items: list[dict]) -> list[dict]:
    seen_ids, seen_titles, out = set(), set(), []
    for item in items:
        iid   = item.get("id", "")
        title = item.get("title", "").lower().strip()[:55]
        if iid in seen_ids or title in seen_titles:
            continue
        seen_ids.add(iid)
        seen_titles.add(title)
        out.append(item)
    return out
