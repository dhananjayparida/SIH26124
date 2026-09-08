"""
SIH26124 - Reset Script
Clears:
  1. All events in SQLite DB (urban_intel.db) -> marks RESOLVED
  2. Fully wipes events + vehicles tables for a clean slate
  3. defect_records.json -> empty list
  4. output/inference_results.json -> empty list
  5. evidence/ folder -> remove all files
"""
import sqlite3, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scratch/ -> project root

DB_PATH        = ROOT / "data" / "urban_intel.db"
DEFECT_JSON    = ROOT / "data" / "defect_records.json"
INFERENCE_JSON = ROOT / "output" / "inference_results.json"
EVIDENCE_DIR   = ROOT / "data" / "evidence"

print("\n" + "="*60)
print("  SIH26124 - CLEARING ALL TEST DATA & QUEUE")
print("="*60)

# ── 1. SQLite DB ─────────────────────────────────────────────
print("\n[1/5] Connecting to:", DB_PATH)
conn = sqlite3.connect(str(DB_PATH))
cur  = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"      Tables found: {tables}")

deleted = {}
for tbl in tables:
    if tbl.startswith("sqlite_"):
        continue
    cur.execute(f"SELECT COUNT(*) FROM [{tbl}]")
    n = cur.fetchone()[0]
    cur.execute(f"DELETE FROM [{tbl}]")
    deleted[tbl] = n
    print(f"      Deleted {n:>5} rows from [{tbl}]")

conn.commit()
conn.close()
print("      DB cleared and committed.")

# ── 2. defect_records.json ────────────────────────────────────
print("\n[2/5] Clearing defect_records.json ...")
if DEFECT_JSON.exists():
    DEFECT_JSON.write_text("[]", encoding="utf-8")
    print("      defect_records.json -> []")
else:
    print("      Not found, skipping.")

# ── 3. inference_results.json ─────────────────────────────────
print("\n[3/5] Clearing inference_results.json ...")
if INFERENCE_JSON.exists():
    INFERENCE_JSON.write_text("[]", encoding="utf-8")
    print("      inference_results.json -> []")
else:
    print("      Not found, skipping.")

# ── 4. evidence/ folder ───────────────────────────────────────
print("\n[4/5] Clearing evidence/ folder ...")
if EVIDENCE_DIR.exists():
    files = list(EVIDENCE_DIR.iterdir())
    count = 0
    for f in files:
        if f.is_file():
            f.unlink()
            count += 1
        elif f.is_dir():
            shutil.rmtree(f)
            count += 1
    print(f"      Removed {count} items from evidence/")
else:
    print("      evidence/ not found, skipping.")

# ── 5. Done ───────────────────────────────────────────────────
print("\n[5/5] Verifying DB is empty ...")
conn = sqlite3.connect(str(DB_PATH))
cur  = conn.cursor()
for tbl in deleted:
    cur.execute(f"SELECT COUNT(*) FROM [{tbl}]")
    n = cur.fetchone()[0]
    status = "OK (empty)" if n == 0 else f"WARNING: {n} rows remain"
    print(f"      [{tbl}]: {status}")
conn.close()

print("\n" + "="*60)
print("  DONE - Queue and all test data cleared!")
print("="*60)
print("\n  Refresh the dashboard at http://localhost:3000")
print("  The maintenance queue will now be empty.\n")
