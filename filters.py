"""
filters.py  —  Strict relevance filtering
Keeps only opportunities that genuinely match Glenn's profile.
Aggressively excludes noise: construction, transportation, sales, sewer, HR, etc.
"""

# ── Hard exclude — if ANY of these appear, drop the opportunity ────────────────
HARD_EXCLUDE_TERMS = [
    # Construction & trades
    "construction worker", "carpenter", "electrician", "plumber", "welder",
    "ironworker", "laborer", "concrete", "masonry", "roofer", "hvac technician",
    "elevator", "pipefitter", "insulation",
    # Transportation
    "truck driver", "cdl", "bus driver", "transit operator", "chauffeur",
    "freight", "logistics coordinator", "dispatcher", "delivery driver",
    "transportation planner" , "traffic engineer",  # too civil-eng focused
    # Sales & marketing
    "sales representative", "account executive", "business development rep",
    "marketing manager", "social media manager", "copywriter", "seo specialist",
    "telemarketer", "insurance agent", "real estate",
    # Healthcare / medical
    "registered nurse", "medical assistant", "pharmacist", "dental",
    "physical therapist", "occupational therapist", "radiologist",
    "physician", "surgeon", "hospital",
    # Food & hospitality
    "chef", "cook", "dishwasher", "server", "bartender", "barista",
    "food service", "restaurant manager", "hotel",
    # Administrative / HR
    "human resources", "hr generalist", "recruiter", "payroll specialist",
    "administrative assistant", "receptionist", "office manager",
    # Utilities & civil
    "sewer", "wastewater", "water treatment plant operator",
    "sanitation worker", "waste management", "landfill",
    "civil engineer" , "structural engineer", "surveyor" ,  # too narrow civil
    # Finance
    "accountant", "bookkeeper", "financial analyst", "loan officer",
    "teller", "mortgage", "auditor",
    # Education (too broad)
    "elementary teacher", "kindergarten", "high school teacher",
    "special education", "school counselor",
    # Security / law enforcement
    "police officer", "correctional officer", "security guard",
    "detention officer",
    # Retail
    "retail associate", "store manager", "cashier", "inventory clerk",
]

# ── Require at least ONE of these in title or description ─────────────────────
MUST_HAVE_ANY = [
    # GIS / geospatial
    "gis", "geospatial", "geographic information", "mapping", "cartograph",
    "arcgis", "qgis", "spatial analysis", "geoint", "geodat",
    # Remote sensing
    "remote sensing", "satellite", "satellite imagery", "aerial imagery",
    "multispectral", "hyperspectral", "lidar", "ndvi", "sar", "radar imagery",
    "landsat", "sentinel", "modis", "naip", "imagery analyst",
    # Drone / UAV
    "drone", "uas", "suas", "uav", "unmanned aerial", "aerial survey",
    "aerial mapping", "part 107", "photogrammetry", "drone2map",
    # Computer vision / AI
    "object detection", "object classification", "object tracking",
    "pixel classification", "semantic segmentation", "computer vision",
    "machine learning", "deep learning", "neural network", "geoai",
    "image analysis", "image classification", "feature extraction",
    # Space / astronomy / UAP
    "astronomy", "astrophysics", "telescope", "space science", "orbital",
    "nasa", "jpl", "spacecraft", "satellite operations", "uap", "anomalous",
    "seti", "astrobiology", "exoplanet",
    # Environmental / climate (Glenn's background)
    "environmental monitoring", "climate change", "vegetation analysis",
    "land cover", "change detection", "ecological", "watershed", "forestry gis",
    "harmful algae", "wildfire", "natural resources",
    # Programming / data science (only when paired with geo context)
    "python developer", "geospatial python", "arcpy", "fme developer",
    "geospatial developer", "gis developer", "geospatial engineer",
    "geospatial data scientist", "spatial data",
    # Research / academia
    "research scientist", "research engineer", "postdoctoral", "phd fellowship",
    "research assistant", "principal investigator", "geospatial research",
    # Intelligence
    "geospatial intelligence", "imagery intelligence", "imint",
    "geoint analyst", "nga", "nro", "reconnaissance",
]

# ── Soft boost — increases score if present (used for ranking, not filtering) ─
PASSION_TERMS = [
    "uap", "anomalous phenomena", "galileo project", "seti", "astrobiology",
    "space force", "webb telescope", "hubble", "bigelow", "skinwalker",
    "ufology", "unexplained", "phenomenon",
]


def is_relevant(title: str, description: str, source: str = "") -> tuple[bool, str]:
    """
    Returns (is_relevant, reason).
    An opportunity is relevant if:
    1. It does NOT contain any hard-exclude terms
    2. It DOES contain at least one must-have term
    """
    text_lower = f"{title} {description}".lower()

    # Check hard excludes first
    for term in HARD_EXCLUDE_TERMS:
        if term in text_lower:
            return False, f"excluded: '{term}'"

    # Check must-have
    for term in MUST_HAVE_ANY:
        if term in text_lower:
            return True, f"matched: '{term}'"

    # NASA/NOAA/USGS/USFS source gets a pass even without keyword match
    trusted_sources = ["nasa", "noaa", "usgs", "usfs", "nga", "nga", "nga"]
    if any(ts in source.lower() for ts in trusted_sources):
        return True, "trusted source"

    return False, "no relevant keywords found"


def passion_boost(title: str, description: str) -> int:
    """Return extra score points for UAP/astronomy/space passion topics."""
    text_lower = f"{title} {description}".lower()
    return sum(3 for term in PASSION_TERMS if term in text_lower)
