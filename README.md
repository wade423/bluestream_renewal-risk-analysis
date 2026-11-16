# Bulk Community Renewal Risk & Transformation Analysis (Blue Stream Fiber case study)

**[Live dashboard](https://wade423.github.io/bluestream-renewal-risk-analysis/) · [5-minute video walkthrough](LINK_TO_VIDEO) · [Power BI report](powerbi/)**

An end-to-end business analysis project built as a case study for a Business Analyst (Transformation) role at Blue Stream Fiber. It answers three questions a fiber operator with bulk HOA/condo contracts would ask:

1. **Which contract renewals are at risk?** Especially where a competitor (Hotwire Communications) is active.
2. **Did a process change work?** AI work-order triage, measured before vs. after.
3. **Does converting legacy cable communities to fiber pay off?** NPS and trouble calls, before vs. after cut-over.

> **Data disclaimer:** all community-level data is **synthetic**. It is scaled to Blue Stream Fiber's *public* footprint (~500 communities, ~150K households, Florida + Houston). Competitor facts are public and sourced. No internal company data was used. This is independent work, not affiliated with Blue Stream Fiber.

![Renewal risk page](docs/screenshots/renewal_risk.png)

## Key findings (synthetic data)

| Question | Finding |
|---|---|
| Renewal risk | 162 contracts (54K units) renew in the next 24 months; 17 score as high risk |
| AI triage | Truck-roll rate on trouble calls 63.0% → 45.8%; repeat visits 17.4% → 10.3% |
| Fiber conversion | NPS 39.6 → 48.1 and trouble calls −53% in the 3 months after cut-over |
| Upsell | Bottom-quartile fiber communities sit ~3 pts below their region's upgrade take rate |

## What's in the repo

| Folder | Contents |
|---|---|
| `data/` | Star-schema CSVs: `dim_community`, `dim_region`, `dim_month`, `fact_community_monthly` (11.8K rows), `fact_work_orders` (169K rows), plus competitor profile and SQL outputs |
| `sql/` | `01_schema.sql` (star schema DDL) and `02_analysis_queries.sql`: 7 business queries using CTEs, window functions (`LAG`, `NTILE`) and a transparent risk-scoring model |
| `python/` | `generate_data.py` (seeded synthetic data generator) and `load_and_test.py` (loads SQLite and runs every query) |
| `docs/` | `index.html`: standalone interactive dashboard served by GitHub Pages (data and d3 embedded, no build step) |
| `powerbi/` | Power BI Project (PBIP): data model, 5 relationships, 31 DAX measures, 4-page report, custom theme |

## Approach

- **Data model:** star schema with community, region and month dimensions, and monthly-KPI and work-order fact tables.
- **Risk score (0–100):** falling NPS (≤30) + low NPS (≤20) + trouble-call load (≤15) + competitor activity (20) + legacy cable (15). Deliberately simple and explainable; with real data, the weights would be validated against actual lost renewals.
- **Measurement:** before/after comparisons for AI triage and fiber conversion. Limitation: no control group. Next step with real data is a matched comparison against not-yet-converted communities.
- **Tools:** SQL (SQLite), Python (pandas), Power BI (Power Query, DAX). An AI assistant was used to generate the synthetic data and draft SQL; the model, measures and every reported number were built and checked by me.

## Real vs. synthetic

| Element | Status |
|---|---|
| Footprint, markets, bulk HOA business model, AI triage and fiber strategy | Real (public) |
| Hotwire Communications profile | Real (public; community count is a third-party estimate) |
| Community names, units, contracts, NPS, revenue, work orders, AI go-live date | Synthetic |
| Community-level "competitor active" flag | Synthetic (stands in for CRM notes) |

## Live dashboard (GitHub Pages)

Settings → Pages → Source: *Deploy from a branch* → Branch `main`, folder `/docs` → Save. The site appears at `https://wade423.github.io/bluestream-renewal-risk-analysis/` within a minute or two.

## Run it

```bash
python python/generate_data.py   # regenerate data (seeded, reproducible)
python python/load_and_test.py   # build SQLite DB and run all 7 queries
```

**Power BI:** clone to `C:\BlueStream\bluestream-renewal-risk-analysis`, open `powerbi/BlueStream_Renewal_Risk.pbip`, click **Refresh**. If you cloned elsewhere: Transform data → Edit parameters → `DataFolder`.

## Healthcare → telecom

My background is healthcare analytics. The metrics map closely: 30-day readmissions → repeat truck rolls, patient satisfaction → NPS, ED triage → dispatch triage, payer contract renewals → HOA contract renewals.

## Sources

- Blue Stream Fiber footprint & Houston expansion: https://www.bluestreamfiber.com/?p=55080
- Blue Stream Fiber Metis AI work-order triage: https://www.fierce-network.com/broadband/blue-stream-ai-brought-down-sizable-work-order-spend
- Hotwire Communications Houston expansion: https://hotwirecommunications.com/in-the-news/houston-fiber-internet-expansion
- Hotwire bulk model and community count (third-party): https://myutilitysearch.com/?p=7947
