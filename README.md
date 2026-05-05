# 🛰️ RFP and Job Scout — Niche Management LLC

**Glenn Sullivan, GISP** | Local dashboard + GitHub Actions scanner

---

## How it works in 30 seconds

1. **GitHub Actions** runs every weekday at 7 AM → scans SAM.gov, SBIR, Virginia eVA, USAJobs → saves `data/opportunities.json` → emails you a digest
2. You download `opportunities.json` from the GitHub Actions artifact
3. Open `dashboard.html` in any browser → import the file → done
4. When you want to apply: click **Generate Application** → go to GitHub Actions → run the workflow → download your `.docx`

---

## Files

```
RFP_and_Job_Scout/
├── dashboard.html              ← Open this in your browser. No install needed.
├── main.py                     ← Daily scanner orchestrator
├── profile.py                  ← Your credentials, keywords, targets (edit this)
├── filters.py                  ← Strict relevance filter (no noise)
├── tracker.py                  ← Opportunity status tracking
├── requirements.txt
├── package.json                ← Node.js docx dependency
├── scanners/
│   └── scan_all.py             ← SAM.gov + SBIR + eVA + USAJobs scanners
├── generators/
│   ├── make_doc.js             ← Word document builder (Node.js)
│   ├── generate_application.py ← Claude API draft writer
│   └── email_digest.py        ← Daily email sender
├── data/
│   ├── tracker.json            ← Committed to repo, tracks applied/hidden
│   └── opportunities.json      ← Written by scanner, imported to dashboard
├── generated_docs/             ← Your .docx files land here
└── .github/workflows/
    ├── daily_scan.yml          ← Runs 7 AM ET weekdays
    └── generate_application.yml ← Triggered manually to make a .docx
```

---

## Setup (one time, ~30 minutes)

### 1. GitHub repo
```bash
cd RFP_and_Job_Scout
git init
git add .
git commit -m "Initial setup"
git remote add origin https://github.com/YOUR_USERNAME/RFP-and-Job-Scout.git
git push -u origin main
```

### 2. GitHub Secrets
Repo → Settings → Secrets and variables → Actions → New repository secret

| Secret | Value | Required? |
|--------|-------|-----------|
| `GMAIL_USER` | `glenn.sullivan8@gmail.com` | ✅ |
| `GMAIL_APP_PASS` | Gmail App Password (16 chars) | ✅ |
| `ANTHROPIC_API_KEY` | From console.anthropic.com | For .docx drafts |
| `USAJOBS_API_KEY` | From developer.usajobs.gov | For federal jobs |
| `SAM_API_KEY` | From sam.gov profile | Raises rate limits |

### 3. Gmail App Password
Google Account → Security → 2-Step Verification → App Passwords → Mail → Generate

### 4. Enable GitHub Pages (optional — for sharing dashboard)
Repo → Settings → Pages → Source: Deploy from branch → main → /root

### 5. Run your first scan manually
GitHub repo → Actions tab → Daily Opportunity Scan → Run workflow

---

## Using the dashboard

1. After a scan runs, go to: Actions → latest run → Artifacts → download `scan-results`
2. Unzip → find `opportunities.json`
3. Open `dashboard.html` in Chrome/Edge/Firefox
4. Click **Import Data** in the sidebar → select `opportunities.json`
5. Your opportunities load instantly and persist in browser storage

**Dashboard features:**
- Top 10 RFPs + Top 10 Jobs (ranked by relevance)
- Local/Drone section (within 120 miles of Roanoke VA)
- All opportunities table with search + sort (capped at 50 each)
- **Generate Application** → triggers GitHub Actions to make a .docx
- **Mark Applied** → manually mark without generating a doc
- **Save** → bookmark for later
- **Not Interested** → permanently hides from all future views
- **Applied History** → full log with dates
- Sample data button to explore before first scan

---

## Generating a Word document

1. Click **Generate Application** on any opportunity
2. Note the Opportunity ID shown in the modal
3. GitHub → Actions → **Generate Application** → Run workflow
4. Enter the ID and type (rfp or job)
5. ~2 minutes later: Actions → Artifacts → download your `.docx`

The document includes:
- **RFP proposals:** Executive Summary, Technical Approach, Relevant Experience, Key Personnel, Core Capabilities, Why Us — all tailored by Claude to the specific opportunity
- **Job applications:** Cover letter (3-4 paragraphs, specific to role) + full resume page with your experience highlights

---

## NAICS codes to register on SAM.gov
- `541370` — Surveying and Mapping (GIS, drone, remote sensing)
- `541512` — Computer Systems Design (GIS apps, web development)
- `541690` — Other Scientific/Technical Consulting (environmental)
- `541720` — Research & Development in Natural Sciences

*Niche Management LLC · Glenn Sullivan, GISP · Salem, VA · nichemanagementllc.com*
