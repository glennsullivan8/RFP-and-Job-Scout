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
DAYS_BACK       = int(os.getenv("DAYS_BACK", "30"))
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


# ── Dream org watch list (shown in email/dashboard as manual-check reminders) ──
# These are NOT fake job postings — they are "check this page" reminders.
# Only real confirmed postings (from USAJobs API or known active URLs) show
# in the Top 10. The watch list appears as a separate section.

DREAM_ORG_WATCHLIST = [
    # UAP / Space Research — check job pages manually each week
    {"name": "The Galileo Project (Harvard)",
     "jobs_url": "https://galileo.hsites.harvard.edu/job-opportunities",
     "note": "Postdoctoral & researcher roles with Prof. Avi Loeb. Multi-sensor UAP observatory.",
     "type": "UAP Research", "score": 20},
    {"name": "SETI Institute",
     "jobs_url": "https://www.seti.org/about-us/careers",
     "note": "Research scientist, data analyst, and astronomer roles.",
     "type": "Space Research", "score": 16},
    {"name": "Sol Foundation",
     "jobs_url": "https://thesolfoundation.org",
     "note": "UAP policy and interdisciplinary research positions.",
     "type": "UAP Research", "score": 14},
    {"name": "Bigelow Aerospace",
     "jobs_url": "https://bigelowaerospace.com",
     "note": "Commercial space habitat and sensor R&D roles.",
     "type": "Commercial Space", "score": 11},
    # Defense / Aerospace
    {"name": "Lockheed Martin",
     "jobs_url": "https://www.lockheedmartinjobs.com/search-jobs?k=remote+sensing+GIS",
     "note": "Search remote sensing, GIS, geospatial intelligence roles.",
     "type": "Defense / Aerospace", "score": 13},
    {"name": "Raytheon Technologies (RTX)",
     "jobs_url": "https://careers.rtx.com/global/en/search-results?keywords=remote+sensing",
     "note": "Sensor systems, ISR, geospatial analyst roles.",
     "type": "Defense / Aerospace", "score": 13},
    {"name": "Radiance Technologies",
     "jobs_url": "https://www.radiancetech.com/careers/",
     "note": "Defense remote sensing and geospatial engineer roles.",
     "type": "Defense", "score": 12},
    {"name": "Boeing",
     "jobs_url": "https://jobs.boeing.com/search-jobs?q=remote+sensing+GIS",
     "note": "Space, satellite, UAV, and GIS analyst roles.",
     "type": "Aerospace", "score": 12},
    # Geospatial / Satellite
    {"name": "Maxar Technologies",
     "jobs_url": "https://maxar.wd1.myworkdayjobs.com/maxar",
     "note": "Object detection, GeoAI, satellite imagery analyst roles.",
     "type": "Space / Geospatial", "score": 15},
    {"name": "Planet Labs",
     "jobs_url": "https://www.planet.com/company/careers/",
     "note": "Remote sensing, GIS, satellite data science roles.",
     "type": "Space / Geospatial", "score": 14},
    {"name": "Esri",
     "jobs_url": "https://www.esri.com/en-us/about/careers/job-search#@criteriaN=200003980",
     "note": "ArcGIS developer, GIS engineer, product specialist roles.",
     "type": "GIS Technology", "score": 14},
    # Virginia Tech
    {"name": "Virginia Tech — Faculty & Research Positions",
     "jobs_url": "https://careers.vt.edu",
     "note": "Adjunct lecturer (GIS/Remote Sensing), research scientist, PhD RA positions.",
     "type": "Teaching / Research", "score": 16},
    {"name": "Virginia Tech — Graduate Admissions (PhD)",
     "jobs_url": "https://geography.vt.edu/graduate.html",
     "note": "Funded PhD RA in geospatial, remote sensing, environmental analysis. 40 min away!",
     "type": "PhD / Research", "score": 17},
    {"name": "NASA JPL — Opportunities",
     "jobs_url": "https://www.jpl.nasa.gov/careers",
     "note": "Research scientist, engineer, and postdoc roles at Jet Propulsion Lab.",
     "type": "Space Research", "score": 20},
    {"name": "NASA FINESST Fellowship",
     "jobs_url": "https://science.nasa.gov/researchers/solicitations/roses-2024/",
     "note": "~$50k/yr research fellowship. Glenn's NASA MTRI background is competitive.",
     "type": "Fellowship", "score": 18},
    # ── University research job boards ──────────────────────────────────────
    # Your alma mater
    {"name": "University of Michigan — Remote Sensing & GIS Research",
     "jobs_url": "https://careers.umich.edu/",
     "note": "Glenn's alma mater. Check SNRE, Geography, EECS, and CLASP departments. Also: MTRI (Michigan Tech Research Institute) where Glenn worked NASA projects.",
     "type": "University Research", "score": 17},
    {"name": "U of Michigan — SNRE / SEAS Research Positions",
     "jobs_url": "https://seas.umich.edu/research/research-positions",
     "note": "School for Environment & Sustainability — remote sensing, environmental modeling, and GIS faculty/research scientist postings.",
     "type": "University Research", "score": 16},
    # Top remote sensing programs
    {"name": "Stanford University — Earth System Science / Remote Sensing",
     "jobs_url": "https://earth.stanford.edu/research/jobs",
     "note": "Stanford ESS and the Hansen Lab. Remote sensing, satellite data, GeoAI, and climate systems research. Also check Stanford HAI for GeoAI positions.",
     "type": "University Research", "score": 18},
    {"name": "MIT — Earth, Atmospheric & Planetary Sciences / CSAIL",
     "jobs_url": "https://careers.mit.edu/",
     "note": "MIT EAPS and Computer Science AI Lab. Remote sensing algorithms, satellite data science, GeoAI. Also check MIT Lincoln Laboratory for defense remote sensing.",
     "type": "University Research", "score": 18},
    {"name": "Harvard University — Center for Geographic Analysis / Galileo Project",
     "jobs_url": "https://galileo.hsites.harvard.edu/job-opportunities",
     "note": "Galileo Project (UAP research with Prof. Avi Loeb) + Center for Geographic Analysis. Check both — Galileo posts sensor/remote sensing research roles.",
     "type": "University Research / UAP", "score": 20},
    {"name": "UC Berkeley — ESPM / Geography / Berkeley Seismological Lab",
     "jobs_url": "https://jobs.berkeley.edu/",
     "note": "Strong remote sensing, environmental modeling, and geospatial AI programs. Also check Berkeley AI Research (BAIR) for GeoAI research scientist roles.",
     "type": "University Research", "score": 17},
    {"name": "University of Colorado Boulder — CIRES / LASP",
     "jobs_url": "https://jobs.colorado.edu/",
     "note": "CIRES (Cooperative Institute for Research in Environmental Sciences) and LASP (Laboratory for Atmospheric & Space Physics). Excellent satellite remote sensing research groups.",
     "type": "University Research", "score": 17},
    {"name": "Colorado State University — CIRA / Atmospheric Science",
     "jobs_url": "https://jobs.colostate.edu/",
     "note": "CIRA (Cooperative Institute for Research in the Atmosphere) — strong NOAA-partnered satellite and remote sensing research. Environmental intelligence and hazard monitoring.",
     "type": "University Research", "score": 16},
    {"name": "Penn State — Geography / Earth & Environmental Systems",
     "jobs_url": "https://hr.psu.edu/careers",
     "note": "Top-ranked geography and remote sensing program. Strong NASA and NOAA partnerships. Check GeoVISTA Center and Earth & Environmental Systems Institute (EESI).",
     "type": "University Research", "score": 17},
    {"name": "USC — Spatial Sciences Institute / Viterbi School",
     "jobs_url": "https://usccareers.usc.edu/",
     "note": "USC Spatial Sciences Institute (SSI) — one of the top GIS and spatial data science programs in the US. Research scientist and faculty positions in geospatial AI and remote sensing.",
     "type": "University Research", "score": 17},
    # Additional strong programs Claude recommends
    {"name": "University of Maryland — ESSIC / GEOG Dept",
     "jobs_url": "https://geog.umd.edu/resources/job-opportunities",
     "note": "Earth System Science Interdisciplinary Center (ESSIC) has strong NASA/NOAA partnerships. UMD Geography maintains an excellent job board: geog.umd.edu/resources/job-opportunities",
     "type": "University Research", "score": 17},
    {"name": "George Mason University — Geography & GeoInfo Science",
     "jobs_url": "https://jobs.gmu.edu/",
     "note": "Center for Spatial Information Science and Systems. Near DC with strong NGA and DoD connections. Remote sensing, GeoAI, and geospatial intelligence focus.",
     "type": "University Research", "score": 16},
    {"name": "Ohio State University — Byrd Polar & Climate Research / Geography",
     "jobs_url": "https://hr.osu.edu/careers/",
     "note": "Strong LiDAR, satellite remote sensing, and polar science programs. Byrd Polar Center does important glacier and climate remote sensing research.",
     "type": "University Research", "score": 15},
    {"name": "University of Arizona — Lunar & Planetary Lab / Steward Observatory",
     "jobs_url": "https://hr.arizona.edu/careers",
     "note": "LPL and Steward Observatory post research scientist and postdoc roles in planetary remote sensing, UAP-adjacent anomaly detection, and astronomical instrumentation.",
     "type": "University Research / Space", "score": 16},
    {"name": "Texas A&M — TAMU Geography / Remote Sensing Center",
     "jobs_url": "https://jobs.tamu.edu/",
     "note": "One of the top US remote sensing research programs. Strong agricultural, environmental, and hazard remote sensing focus. NOAA and USDA partnerships.",
     "type": "University Research", "score": 15},
    {"name": "University of Wisconsin-Madison — SSEC / Nelson Institute",
     "jobs_url": "https://jobs.wisc.edu/",
     "note": "Space Science & Engineering Center (SSEC) — strong satellite remote sensing and atmospheric science. CIMSS (Cooperative Institute for Meteorological Satellite Studies) NOAA partner.",
     "type": "University Research", "score": 16},
    # Key job boards to check weekly
    {"name": "AAG Career Center (American Assoc of Geographers)",
     "jobs_url": "https://jobs.aag.org/jobs/",
     "note": "Best single job board for university GIS/remote sensing research positions. Updated frequently. Always check this weekly.",
     "type": "Job Board", "score": 15},
    {"name": "AGU Career Center (American Geophysical Union)",
     "jobs_url": "https://findajob.agu.org/jobs/",
     "note": "Best board for earth science, remote sensing, and space research positions. Covers postdocs, research scientists, and faculty at universities and labs.",
     "type": "Job Board", "score": 15},
    {"name": "USGIF Job Board (Geospatial Intelligence Foundation)",
     "jobs_url": "https://usgif.org/careers/",
     "note": "Geospatial intelligence and GEOINT-focused jobs. Strong DoD/NGA pipeline. Internship and full-time research roles.",
     "type": "Job Board / GEOINT", "score": 14},
]


def _build_watchlist_reminders() -> list[dict]:
    """
    Build watch list entries. These show as a SEPARATE section in the email
    and dashboard — clearly labeled as 'check this page' not confirmed postings.
    Scored slightly lower so real USAJobs postings always rank above them.
    """
    items = []
    for org in DREAM_ORG_WATCHLIST:
        items.append({
            "id": _make_id("watch", org["name"]),
            "type": "job",
            "source": "Watch List",
            "title": f"Check for openings: {org['name']}",
            "org": org["name"],
            "posted": "",
            "deadline": "Check page",
            "description": org["note"],
            "score": org["score"],
            "matched_kws": ["remote sensing", "gis", "research"],
            "url": org["jobs_url"],
            "salary": "Competitive / Stipend",
            "location": "Various",
            "remote": True,
            "job_type": org["type"],
            "is_watchlist": True,
        })
    return items


# ── Virginia Tech curated RFP / funding opportunities ─────────────────────────

VT_RFP_TARGETS = [
    {"id":"vt-rfp-vtrc","type":"rfp","source":"Virginia Tech — VTRC",
     "title":"VT Transportation Research Council — Drone & GIS Contracts",
     "org":"Virginia Tech / VTRC","posted":"","deadline":"Ongoing",
     "description":"VTRC regularly issues contracts for drone survey, GIS, remote sensing, and geospatial data management. 40 min from Salem VA — perfect for Niche Management LLC.",
     "score":22,"matched_kws":["drone","gis","remote sensing","aerial survey","virginia tech"],
     "url":"https://vtrc.vt.edu/","set_aside":"Small Business / Research","naics":"541370","is_local":True,"is_drone":True},
    {"id":"vt-rfp-research","type":"rfp","source":"Virginia Tech — Research Office",
     "title":"VT Office of Research — Geospatial & Remote Sensing Subcontracts",
     "org":"Virginia Tech","posted":"","deadline":"Ongoing",
     "description":"VT Research Office issues subcontracts for geospatial AI, remote sensing, environmental monitoring, and UAV research. Co-investigator and consultant roles for industry partners.",
     "score":20,"matched_kws":["remote sensing","geoai","research","virginia tech","funding"],
     "url":"https://research.vt.edu/","set_aside":"Research Collaboration","naics":"541720","is_local":True,"is_drone":False},
    {"id":"vt-rfp-finesst","type":"rfp","source":"NASA FINESST via Virginia Tech",
     "title":"NASA FINESST Fellowship — Earth & Space Science (via VT)",
     "org":"NASA / Virginia Tech","posted":"","deadline":"See NASA ROSES",
     "description":"NASA FINESST pays ~50k/yr stipend. Glenn's NASA MTRI + LiDAR/NDVI background makes him competitive. Pursue through Virginia Tech as host institution.",
     "score":24,"matched_kws":["nasa","fellowship","remote sensing","research","virginia tech","lidar"],
     "url":"https://science.nasa.gov/researchers/solicitations/roses-2024/","set_aside":"NASA Fellowship","naics":"541720","is_local":True,"is_drone":False},
    {"id":"vt-rfp-ipg","type":"rfp","source":"Virginia Tech — VTIPG",
     "title":"VT Institute for Policy & Governance — Geospatial Research Contracts",
     "org":"Virginia Tech / VTIPG","posted":"","deadline":"Ongoing",
     "description":"VTIPG issues research contracts in environmental monitoring, land use, geospatial policy, and remote sensing applications.",
     "score":18,"matched_kws":["geospatial","remote sensing","environmental monitoring","research","virginia tech"],
     "url":"https://vtipg.org/","set_aside":"Research Contract","naics":"541690","is_local":True,"is_drone":False},
]

def _scan_vt_opportunities() -> list[dict]:
    logger.info(f"Virginia Tech targets: {len(VT_RFP_TARGETS)} curated opportunities")
    return VT_RFP_TARGETS


# ── Main entry ─────────────────────────────────────────────────────────────────

def run_all_scans() -> tuple[list[dict], list[dict]]:
    """
    Returns (rfps, jobs) — each filtered, deduplicated, sorted by score.
    Hidden opportunities are removed. All remaining are marked as seen.
    """
    logger.info("Starting full scan...")

    # Gather
    raw_rfps = _scan_sam() + _scan_sbir() + _scan_eva() + _scan_vt_opportunities()
    raw_jobs = _scan_usajobs() + _build_watchlist_reminders()

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
