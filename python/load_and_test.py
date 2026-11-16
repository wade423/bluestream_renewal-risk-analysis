"""Load the CSVs into SQLite (bluestream.db) and run every analysis query."""
import sqlite3, re
import pandas as pd
from pathlib import Path

base = Path(__file__).parent.parent
db = base / "bluestream.db"
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
con.executescript((base / "sql/01_schema.sql").read_text())
for t in ["dim_region", "dim_community", "dim_month", "fact_community_monthly",
          "fact_work_orders", "ref_competitor_profile"]:
    pd.read_csv(base / f"data/{t}.csv").to_sql(t, con, if_exists="append", index=False)

sql = (base / "sql/02_analysis_queries.sql").read_text()
blocks = re.split(r"\n-- =+\n-- (Q\d+\..*?)\n", sql)
pd.set_option("display.width", 220, "display.max_columns", 30)
for i in range(1, len(blocks), 2):
    title, body = blocks[i], blocks[i + 1]
    body = re.sub(r"^--.*$", "", body, flags=re.M).strip()
    print(f"\n### {title}")
    print(pd.read_sql(body, con).head(12).to_string(index=False))
con.close()
