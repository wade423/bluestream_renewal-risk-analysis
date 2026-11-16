"""
Synthetic data generator - Blue Stream Fiber Business Analyst portfolio project.

ALL ROWS ARE FICTIONAL. Totals are scaled to Blue Stream Fiber's PUBLIC footprint
(~500 communities, ~150,000 households, Florida + Houston). Community names are
invented. No internal company data was used.

Run:  python generate_data.py   -> writes CSVs to ./data
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(423)
OUT = Path(__file__).parent.parent / "data"
OUT.mkdir(exist_ok=True)

MONTHS = pd.date_range("2024-11-01", "2026-10-01", freq="MS")  # 24 months
AI_ROLLOUT = pd.Timestamp("2025-07-01")  # synthetic go-live for AI work-order triage

# ---------------------------------------------------------------- regions
regions = pd.DataFrame([
    # region_id, name, state, hub city, n communities, hotwire present (public), market_launch
    ("SFL", "South Florida",     "FL", "Coral Springs",   150, 1, "1978-01-01"),
    ("TCO", "Treasure Coast",    "FL", "Port St. Lucie",  110, 0, "1985-01-01"),
    ("CFL", "Central Florida",   "FL", "Orlando",          90, 1, "2005-01-01"),
    ("SWF", "Southwest Florida", "FL", "Fort Myers",       70, 1, "2008-01-01"),
    ("GCS", "Gulf Coast",        "FL", "Venice",           50, 1, "2012-01-01"),
    ("HOU", "Houston",           "TX", "Houston",          30, 1, "2024-09-01"),
], columns=["region_id", "region_name", "state", "hub_city", "n_comm",
            "hotwire_present_public", "market_launch_date"])

# ---------------------------------------------------------------- community names (invented)
pre = ["Palm", "Heron", "Cypress", "Coral", "Egret", "Mangrove", "Osprey", "Sabal", "Magnolia",
       "Pelican", "Banyan", "Seagrape", "Ibis", "Live Oak", "Sawgrass", "Tarpon", "Manatee",
       "Willow", "Juniper", "Bluewater", "Sandpiper", "Laurel", "Cedar", "Orchid", "Hibiscus",
       "Silver Lake", "Eagle", "Stone", "Harbor", "Crescent", "Fox", "Bay", "Lantana", "Tortoise"]
suf = ["Pointe", "Reserve", "Landing", "Isles", "Preserve", "Village", "Crossing", "Estates",
       "Commons", "Shores", "Trace", "Hammock", "Lakes", "Run", "Cove", "Park", "Ridge", "Bend"]
names = set()
while len(names) < 500:
    names.add(f"{rng.choice(pre)} {rng.choice(suf)}")
names = sorted(names)
rng.shuffle(names)

TYPES = ["HOA - Single Family", "COA - Condominium", "55+ Active Adult",
         "Master-Planned New Construction", "Multifamily / Apartment"]

rows, i = [], 0
for _, r in regions.iterrows():
    for _ in range(r.n_comm):
        i += 1
        if r.region_id == "HOU":
            ctype = rng.choice(TYPES[3:], p=[0.4, 0.6])
        else:
            ctype = rng.choice(TYPES, p=[0.34, 0.24, 0.18, 0.12, 0.12])
        units = int(np.clip(rng.lognormal(5.42, 0.6), 60, 1500))
        if ctype == "55+ Active Adult":
            units = int(units * 1.6)

        # build type: native FTTH / converted HFC->FTTH / legacy HFC still pending
        conv_date = pd.NaT
        if r.region_id == "HOU" or ctype == "Master-Planned New Construction":
            build = "Native FTTH"
        else:
            build = rng.choice(["Native FTTH", "Converted HFC to FTTH", "Legacy HFC"],
                               p=[0.30, 0.52, 0.18])
            if build == "Converted HFC to FTTH":
                # ~35% converted inside the 24-month window -> shows before/after
                if rng.random() < 0.35:
                    conv_date = rng.choice(MONTHS[2:20])
                else:
                    conv_date = pd.Timestamp("2019-01-01") + pd.Timedelta(days=int(rng.integers(0, 2000)))

        # contract
        if r.region_id == "HOU":
            start = pd.Timestamp("2024-09-01") + pd.DateOffset(months=int(rng.integers(0, 22)))
        else:
            start = pd.Timestamp("2016-01-01") + pd.Timedelta(days=int(rng.integers(0, 3400)))
        term = int(rng.choice([5, 7, 10], p=[0.35, 0.35, 0.30]))
        end = start + pd.DateOffset(years=term)
        renewals = 0
        while end < pd.Timestamp("2026-11-01"):      # expired contracts were renewed
            start, end, renewals = end, end + pd.DateOffset(years=term), renewals + 1
        # make sure a meaningful renewal pipeline lands in the next 24 months
        if r.region_id != "HOU" and rng.random() < 0.0:
            end = pd.Timestamp("2026-11-01") + pd.Timedelta(days=int(rng.integers(0, 730)))
            start = end - pd.DateOffset(years=term)

        tier = int(rng.choice([300, 500, 1000], p=[0.25, 0.45, 0.30]))
        if build == "Legacy HFC":
            tier = int(rng.choice([300, 500], p=[0.7, 0.3]))
        rate = round(float(rng.normal(52 if tier == 300 else 58 if tier == 500 else 66, 4)), 2)

        # synthetic competitive signal (NOT real Hotwire data)
        comp_activity = int(r.hotwire_present_public == 1 and rng.random() < 0.22)

        rows.append(dict(
            community_id=f"C{i:04d}", community_name=names[i - 1], region_id=r.region_id,
            community_type=ctype, total_units=units, build_type=build,
            fiber_conversion_date=conv_date, contract_start_date=start.normalize(),
            contract_end_date=end.normalize(), contract_term_years=term, times_renewed=renewals,
            bulk_tier_mbps=tier, bulk_rate_per_door=rate,
            competitor_activity_flag=comp_activity,
        ))
comm = pd.DataFrame(rows)

# Houston go-live = contract start
comm["go_live_month"] = np.where(
    comm.region_id == "HOU", comm.contract_start_date.values.astype("datetime64[M]"),
    np.datetime64("2000-01-01"))
comm["go_live_month"] = pd.to_datetime(comm["go_live_month"])

# latent community health (drives NPS + tickets); a deteriorating group creates renewal risk
comm["base_nps"] = rng.normal(48, 12, len(comm))
comm.loc[comm.build_type == "Legacy HFC", "base_nps"] -= 14
comm.loc[comm.community_type == "55+ Active Adult", "base_nps"] += 5
decliners = rng.random(len(comm)) < 0.10
decliners |= (comm.competitor_activity_flag == 1) & (rng.random(len(comm)) < 0.45)
comm["nps_trend_per_month"] = np.where(decliners, rng.uniform(-1.6, -0.6, len(comm)),
                                       rng.normal(0.25, 0.15, len(comm)))

# ---------------------------------------------------------------- work orders
WO_TYPES = ["Trouble Call", "Install", "Speed Upgrade", "Move / Transfer", "Equipment Swap"]
wo_rows, kpi_rows, wo_id = [], [], 0
for _, c in comm.iterrows():
    for m in MONTHS:
        if m < c.go_live_month:
            continue
        months_live = (m.year - c.go_live_month.year) * 12 + m.month - c.go_live_month.month
        ramp = min(1.0, 0.35 + 0.08 * months_live) if c.region_id == "HOU" else 1.0
        active = int(c.total_units * rng.uniform(0.90, 0.97) * ramp)

        on_fiber = c.build_type == "Native FTTH" or (
            c.build_type == "Converted HFC to FTTH" and pd.notna(c.fiber_conversion_date)
            and m >= c.fiber_conversion_date)
        t = MONTHS.get_loc(m)
        nps = c.base_nps + c.nps_trend_per_month * t - (9 if not on_fiber and c.build_type == "Converted HFC to FTTH" else 0)
        nps = float(np.clip(nps + rng.normal(0, 4), -40, 90))

        trouble_rate = 0.018 if on_fiber else 0.034
        trouble_rate *= (1 + max(0, 45 - nps) / 60)          # unhappy communities call more
        n_trouble = rng.poisson(active * trouble_rate)
        n_install = rng.poisson(active * 0.010 * (3 if c.region_id == "HOU" and months_live < 8 else 1))
        n_upgrade = rng.poisson(active * 0.006 * (1.4 if on_fiber else 0.5))
        n_move = rng.poisson(active * 0.004)
        n_equip = rng.poisson(active * 0.003)

        ai_live = m >= AI_ROLLOUT
        ai_share = 0 if not ai_live else min(0.72, 0.30 + 0.06 * ((m - AI_ROLLOUT).days // 30))

        counts = dict(zip(WO_TYPES, [n_trouble, n_install, n_upgrade, n_move, n_equip]))
        stats = dict(trouble=0, rolls=0, repeats=0, ai=0)
        for wtype, n in counts.items():
            for _ in range(n):
                wo_id += 1
                day = int(rng.integers(0, m.days_in_month))
                ai = bool(rng.random() < ai_share)
                if wtype == "Trouble Call":
                    p_roll = (0.42 if ai_live else 0.56) * (1.0 if on_fiber else 1.25)
                    roll = rng.random() < min(p_roll, 0.9)
                    p_rep = (0.09 if ai_live else 0.14) * (1.0 if on_fiber else 1.4)
                    repeat = roll and rng.random() < p_rep
                    remote = not roll
                else:
                    roll = wtype in ("Install", "Equipment Swap") or (wtype == "Move / Transfer" and rng.random() < 0.5)
                    repeat = roll and rng.random() < 0.04
                    remote = not roll
                triage_min = round(float(rng.gamma(2, 1.2)) if ai else float(rng.gamma(4, 6.0)), 1)
                wo_rows.append((f"WO{wo_id:07d}", c.community_id,
                                (m + pd.Timedelta(days=day)).date(), wtype, int(ai), triage_min,
                                int(roll), int(remote), int(repeat)))
                if wtype == "Trouble Call":
                    stats["trouble"] += 1
                stats["rolls"] += int(roll)
                stats["repeats"] += int(repeat)
                stats["ai"] += int(ai)

        take = (0.10 + 0.0025 * t) * (1.5 if on_fiber else 0.6) * (1 + (nps - 45) / 200)
        upg_subs = int(active * float(np.clip(take + rng.normal(0, 0.01), 0.01, 0.6)))
        kpi_rows.append(dict(
            community_id=c.community_id, month=m.date(), active_units=active, on_fiber=int(on_fiber),
            nps=round(nps, 1), upgrade_subscribers=upg_subs,
            upgrade_revenue=round(upg_subs * float(rng.normal(31, 2)), 2),
            bulk_revenue=round(active * c.bulk_rate_per_door, 2),
            referral_leads=int(rng.poisson(0.08 + max(0, nps - 50) / 250)),
            google_reviews_5star=int(rng.poisson(max(0.2, active / 400 * (nps + 40) / 90))),
        ))

wo = pd.DataFrame(wo_rows, columns=["work_order_id", "community_id", "created_date", "work_order_type",
                                    "ai_triaged", "triage_minutes", "truck_roll",
                                    "resolved_remotely", "repeat_within_30d"])
kpi = pd.DataFrame(kpi_rows)

# ---------------------------------------------------------------- competitor table (PUBLIC facts only)
competitors = pd.DataFrame([
    ("Blue Stream Fiber", "Coral Springs, FL", "1978 (as Advanced Cable)", "Private",
     "~500 communities / ~150,000 households / ~385,000 residents",
     "FL + Houston (entered Sept 2024)", "Bulk HOA/COA/MDU + retail",
     "Metis AI work-order triage; Ateme OTT w/ dynamic ad insertion",
     "https://www.bluestreamfiber.com/?p=55080"),
    ("Hotwire Communications (Fision)", "Fort Lauderdale, FL", "2002", "Blackstone-backed (2021)",
     "1,180+ communities (third-party estimate)",
     "FL (South, Central, SW, Suncoast, North) + Houston + other states",
     "Bulk HOA/COA/MDU, master-planned, hospitality, student housing",
     "On-site account managers; up to 8 Gig tier",
     "https://hotwirecommunications.com/in-the-news/houston-fiber-internet-expansion"),
], columns=["provider", "headquarters", "founded", "ownership", "footprint", "markets",
            "business_model", "notable_differentiators", "source_url"])

month_dim = pd.DataFrame({"month": MONTHS.date})
month_dim["year"] = MONTHS.year
month_dim["month_num"] = MONTHS.month
month_dim["month_label"] = MONTHS.strftime("%b %Y")
month_dim["ai_period"] = np.where(MONTHS >= AI_ROLLOUT, "Post-AI", "Pre-AI")

# ---------------------------------------------------------------- write
comm_out = comm.drop(columns=["base_nps", "nps_trend_per_month", "go_live_month"])
for col in ["fiber_conversion_date", "contract_start_date", "contract_end_date"]:
    comm_out[col] = pd.to_datetime(comm_out[col]).dt.date
regions.drop(columns=["n_comm"]).to_csv(OUT / "dim_region.csv", index=False)
comm_out.to_csv(OUT / "dim_community.csv", index=False)
month_dim.to_csv(OUT / "dim_month.csv", index=False)
kpi.to_csv(OUT / "fact_community_monthly.csv", index=False)
wo.to_csv(OUT / "fact_work_orders.csv", index=False)
competitors.to_csv(OUT / "ref_competitor_profile.csv", index=False)

print("communities", len(comm_out), "units", comm_out.total_units.sum())
print("monthly rows", len(kpi), "work orders", len(wo))
