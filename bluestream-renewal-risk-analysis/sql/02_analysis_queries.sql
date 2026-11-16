-- Blue Stream Fiber BA portfolio project — analysis queries (SYNTHETIC DATA)
-- As-of date for the analysis: 2026-11-01. Written for SQLite.
-- SQL Server equivalents: date(x,'+24 months') -> DATEADD(month, 24, x);
--                         julianday(a)-julianday(b) -> DATEDIFF(day, b, a);  || -> CONCAT / +


-- ============================================================
-- Q1. Portfolio health by region (latest month)
--     Business question: where is the base strongest and weakest today?
-- ============================================================
WITH latest AS (
    SELECT * FROM fact_community_monthly WHERE month = '2026-10-01'
)
SELECT r.region_name,
       COUNT(*)                                                  AS communities,
       SUM(l.active_units)                                       AS active_units,
       ROUND(SUM(l.nps * l.active_units) / SUM(l.active_units), 1) AS nps_weighted,
       ROUND(100.0 * SUM(l.upgrade_subscribers) / SUM(l.active_units), 1) AS upgrade_take_rate_pct,
       ROUND(100.0 * SUM(l.on_fiber * l.active_units) / SUM(l.active_units), 1) AS pct_units_on_fiber,
       ROUND(SUM(l.bulk_revenue + l.upgrade_revenue) / 1000.0, 1) AS monthly_revenue_k
FROM latest l
JOIN dim_community c ON c.community_id = l.community_id
JOIN dim_region    r ON r.region_id    = c.region_id
GROUP BY r.region_name
ORDER BY active_units DESC;


-- ============================================================
-- Q2. Renewal risk scoring for contracts ending in the next 24 months
--     Business question: which renewals should account teams work first?
--     Score (0-100) = NPS decline + service pain + competitive pressure + legacy plant
-- ============================================================
WITH nps_trend AS (
    SELECT community_id,
           AVG(CASE WHEN month >= '2026-08-01' THEN nps END) AS nps_last3,
           AVG(CASE WHEN month BETWEEN '2026-02-01' AND '2026-04-01' THEN nps END) AS nps_prior3
    FROM fact_community_monthly
    GROUP BY community_id
),
service AS (
    SELECT community_id,
           SUM(CASE WHEN work_order_type = 'Trouble Call' THEN 1 ELSE 0 END) AS trouble_calls_90d,
           SUM(repeat_within_30d) AS repeat_rolls_90d,
           SUM(truck_roll)        AS truck_rolls_90d
    FROM fact_work_orders
    WHERE created_date >= '2026-08-01'
    GROUP BY community_id
),
base AS (
    SELECT c.community_id, c.community_name, r.region_name, c.community_type, c.total_units,
           c.build_type, c.contract_end_date, c.competitor_activity_flag,
           ROUND(n.nps_last3, 1)                       AS nps_last3,
           ROUND(n.nps_last3 - n.nps_prior3, 1)        AS nps_change_6mo,
           ROUND(100.0 * s.trouble_calls_90d / c.total_units, 1) AS trouble_per_100_units_90d,
           ROUND(100.0 * s.repeat_rolls_90d / NULLIF(s.truck_rolls_90d, 0), 1) AS repeat_roll_pct
    FROM dim_community c
    JOIN dim_region r ON r.region_id = c.region_id
    JOIN nps_trend  n ON n.community_id = c.community_id
    LEFT JOIN service s ON s.community_id = c.community_id
    WHERE c.contract_end_date >= '2026-11-01'
      AND c.contract_end_date <  date('2026-11-01', '+24 months')
),
scored AS (
    SELECT *,
           MIN(30, MAX(0, -nps_change_6mo * 2))                      -- falling NPS: up to 30
         + MIN(20, MAX(0, (45 - nps_last3) * 0.8))                   -- low NPS: up to 20
         + MIN(15, trouble_per_100_units_90d * 1.5)                  -- ticket load: up to 15
         + CASE WHEN competitor_activity_flag = 1 THEN 20 ELSE 0 END -- competitor in play
         + CASE WHEN build_type = 'Legacy HFC' THEN 15 ELSE 0 END    -- not yet on fiber
           AS risk_score
    FROM base
)
SELECT *,
       CASE WHEN risk_score >= 50 THEN 'High'
            WHEN risk_score >= 25 THEN 'Medium'
            ELSE 'Low' END AS risk_tier,
       ROUND(julianday(contract_end_date) - julianday('2026-11-01')) AS days_to_renewal
FROM scored
ORDER BY risk_score DESC, contract_end_date
LIMIT 25;


-- ============================================================
-- Q3. Early warning: communities with NPS down 3 months in a row
--     (window function: LAG)
-- ============================================================
WITH lagged AS (
    SELECT community_id, month, nps,
           LAG(nps, 1) OVER (PARTITION BY community_id ORDER BY month) AS nps_m1,
           LAG(nps, 2) OVER (PARTITION BY community_id ORDER BY month) AS nps_m2,
           LAG(nps, 3) OVER (PARTITION BY community_id ORDER BY month) AS nps_m3
    FROM fact_community_monthly
)
SELECT c.community_name, r.region_name, l.month,
       ROUND(l.nps_m3, 1) AS nps_3mo_ago, ROUND(l.nps, 1) AS nps_now,
       c.contract_end_date
FROM lagged l
JOIN dim_community c ON c.community_id = l.community_id
JOIN dim_region r    ON r.region_id    = c.region_id
WHERE l.month = '2026-10-01'
  AND l.nps < l.nps_m1 AND l.nps_m1 < l.nps_m2 AND l.nps_m2 < l.nps_m3
ORDER BY (l.nps - l.nps_m3);


-- ============================================================
-- Q4. Transformation measurement: work-order triage before vs. after AI go-live
--     Business question: did the automation change outcomes, not just cost?
-- ============================================================
SELECT CASE WHEN created_date >= '2025-07-01' THEN 'Post-AI' ELSE 'Pre-AI' END AS period,
       COUNT(*)                                        AS trouble_calls,
       ROUND(100.0 * AVG(ai_triaged), 1)               AS pct_ai_triaged,
       ROUND(AVG(triage_minutes), 1)                   AS avg_triage_minutes,
       ROUND(100.0 * AVG(truck_roll), 1)               AS truck_roll_rate_pct,
       ROUND(100.0 * AVG(resolved_remotely), 1)        AS resolved_remotely_pct,
       ROUND(100.0 * SUM(repeat_within_30d) / SUM(truck_roll), 1) AS repeat_roll_rate_pct
FROM fact_work_orders
WHERE work_order_type = 'Trouble Call'
GROUP BY period
ORDER BY period DESC;


-- ============================================================
-- Q5. Fiber conversion impact: 3 months before vs. 3 months after cut-over
--     (only communities converted inside the data window)
-- ============================================================
WITH conv AS (
    SELECT community_id, community_name, fiber_conversion_date
    FROM dim_community
    WHERE build_type = 'Converted HFC to FTTH'
      AND fiber_conversion_date >= '2025-02-01'
      AND fiber_conversion_date <= '2026-07-01'
),
windows AS (
    SELECT cv.community_id,
           AVG(CASE WHEN m.month <  cv.fiber_conversion_date
                     AND m.month >= date(cv.fiber_conversion_date, '-3 months') THEN m.nps END) AS nps_before,
           AVG(CASE WHEN m.month >= cv.fiber_conversion_date
                     AND m.month <  date(cv.fiber_conversion_date, '+3 months') THEN m.nps END) AS nps_after
    FROM conv cv
    JOIN fact_community_monthly m ON m.community_id = cv.community_id
    GROUP BY cv.community_id
),
tickets AS (
    SELECT cv.community_id,
           SUM(CASE WHEN w.created_date <  cv.fiber_conversion_date
                     AND w.created_date >= date(cv.fiber_conversion_date, '-3 months') THEN 1 ELSE 0 END) AS tickets_before,
           SUM(CASE WHEN w.created_date >= cv.fiber_conversion_date
                     AND w.created_date <  date(cv.fiber_conversion_date, '+3 months') THEN 1 ELSE 0 END) AS tickets_after
    FROM conv cv
    JOIN fact_work_orders w ON w.community_id = cv.community_id AND w.work_order_type = 'Trouble Call'
    GROUP BY cv.community_id
)
SELECT COUNT(*)                                    AS communities_converted,
       ROUND(AVG(w.nps_before), 1)                 AS avg_nps_before,
       ROUND(AVG(w.nps_after), 1)                  AS avg_nps_after,
       SUM(t.tickets_before)                       AS trouble_calls_before,
       SUM(t.tickets_after)                        AS trouble_calls_after,
       ROUND(100.0 * (SUM(t.tickets_after) - SUM(t.tickets_before)) / SUM(t.tickets_before), 1) AS pct_change_trouble_calls
FROM windows w
JOIN tickets t ON t.community_id = w.community_id;


-- ============================================================
-- Q6. Upsell opportunity: fiber communities in the bottom quartile of
--     upgrade take rate within their region (window function: NTILE)
-- ============================================================
WITH latest AS (
    SELECT m.community_id, c.community_name, r.region_name, m.active_units,
           1.0 * m.upgrade_subscribers / m.active_units AS take_rate
    FROM fact_community_monthly m
    JOIN dim_community c ON c.community_id = m.community_id
    JOIN dim_region r    ON r.region_id    = c.region_id
    WHERE m.month = '2026-10-01' AND m.on_fiber = 1
),
ranked AS (
    SELECT *,
           NTILE(4) OVER (PARTITION BY region_name ORDER BY take_rate) AS quartile,
           AVG(take_rate) OVER (PARTITION BY region_name)             AS region_avg_take
    FROM latest
)
SELECT region_name,
       COUNT(*)                                                    AS bottom_quartile_communities,
       SUM(active_units)                                           AS units,
       ROUND(100.0 * AVG(take_rate), 1)                            AS avg_take_rate_pct,
       ROUND(100.0 * AVG(region_avg_take), 1)                      AS region_avg_take_rate_pct,
       -- monthly revenue if these communities reached the regional average at ~$31/upgrade
       ROUND(SUM((region_avg_take - take_rate) * active_units * 31), 0) AS monthly_upside_usd
FROM ranked
WHERE quartile = 1
GROUP BY region_name
ORDER BY monthly_upside_usd DESC;


-- ============================================================
-- Q7. Houston ramp: units and installs by month since market entry
-- ============================================================
SELECT m.month,
       COUNT(DISTINCT m.community_id) AS live_communities,
       SUM(m.active_units)            AS active_units,
       (SELECT COUNT(*) FROM fact_work_orders w
          JOIN dim_community c2 ON c2.community_id = w.community_id
         WHERE c2.region_id = 'HOU' AND w.work_order_type = 'Install'
           AND substr(w.created_date, 1, 7) = substr(m.month, 1, 7)) AS installs
FROM fact_community_monthly m
JOIN dim_community c ON c.community_id = m.community_id
WHERE c.region_id = 'HOU'
GROUP BY m.month
ORDER BY m.month;
