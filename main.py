"""
main.py  —  Niche Management LLC Daily Automation v2
Scans RFPs and jobs, saves JSON for dashboard, sends email digest.
No auto-drafting — Glenn triggers generation manually via dashboard.
"""

import os, sys, json, logging, argparse
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("main")

from scanners.scan_all        import run_all_scans
from generators.email_digest  import send_digest

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


def save_opportunities(rfps: list, jobs: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "generated": datetime.utcnow().isoformat(),
        "rfp_count": len(rfps),
        "job_count":  len(jobs),
        "rfps": rfps,
        "jobs": jobs,
    }
    (DATA_DIR / "opportunities.json").write_text(json.dumps(out, indent=2, default=str))
    logger.info(f"Saved {len(rfps)} RFPs + {len(jobs)} jobs → {DATA_DIR}/opportunities.json")


def print_summary(rfps: list, jobs: list) -> None:
    print("\n" + "="*65)
    print("  NICHE MANAGEMENT LLC — SCAN RESULTS")
    print(f"  {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}")
    print("="*65)
    print(f"\n📡 TOP RFPs ({len(rfps)} total):")
    for r in rfps[:8]:
        local = " 📍" if r.get("is_local") else ""
        print(f"  [{r['score']:2d}] {r['title'][:55]}{local}")
        print(f"       {r.get('org','')[:35]} | {r.get('source','')}")
    print(f"\n💼 TOP JOBS ({len(jobs)} total):")
    for j in jobs[:8]:
        print(f"  [{j['score']:2d}] {j['title'][:55]}")
        print(f"       {j.get('org','')[:35]} | {j.get('job_type','')}")
    print("="*65 + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--no-save",  action="store_true")
    args = parser.parse_args()

    logger.info("🛰️  Starting Niche Management LLC daily scan v2")

    rfps, jobs = run_all_scans()
    print_summary(rfps, jobs)

    if not args.no_save:
        save_opportunities(rfps, jobs)

    if not args.no_email:
        send_digest(rfps, jobs)
    else:
        logger.info("Email skipped (--no-email)")

    logger.info("✅ Done.")


if __name__ == "__main__":
    main()
