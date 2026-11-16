-- Blue Stream Fiber BA portfolio project — star schema (SYNTHETIC DATA)
-- Written for SQLite; SQL Server notes inline where syntax differs.

CREATE TABLE dim_region (
    region_id              TEXT PRIMARY KEY,
    region_name            TEXT NOT NULL,
    state                  TEXT NOT NULL,
    hub_city               TEXT,
    hotwire_present_public INTEGER,          -- 1 = Hotwire publicly lists properties in this region
    market_launch_date     DATE
);

CREATE TABLE dim_community (
    community_id             TEXT PRIMARY KEY,
    community_name           TEXT NOT NULL,   -- invented names
    region_id                TEXT REFERENCES dim_region(region_id),
    community_type           TEXT,
    total_units              INTEGER,
    build_type               TEXT,            -- Native FTTH | Converted HFC to FTTH | Legacy HFC
    fiber_conversion_date    DATE,
    contract_start_date      DATE,
    contract_end_date        DATE,
    contract_term_years      INTEGER,
    times_renewed            INTEGER,
    bulk_tier_mbps           INTEGER,
    bulk_rate_per_door       REAL,
    competitor_activity_flag INTEGER          -- SYNTHETIC: competitor proposal reported to account team
);

CREATE TABLE dim_month (
    month       DATE PRIMARY KEY,
    year        INTEGER,
    month_num   INTEGER,
    month_label TEXT,
    ai_period   TEXT                          -- Pre-AI | Post-AI (synthetic go-live 2025-07-01)
);

CREATE TABLE fact_community_monthly (
    community_id         TEXT REFERENCES dim_community(community_id),
    month                DATE REFERENCES dim_month(month),
    active_units         INTEGER,
    on_fiber             INTEGER,
    nps                  REAL,
    upgrade_subscribers  INTEGER,
    upgrade_revenue      REAL,
    bulk_revenue         REAL,
    referral_leads       INTEGER,
    google_reviews_5star INTEGER,
    PRIMARY KEY (community_id, month)
);

CREATE TABLE fact_work_orders (
    work_order_id     TEXT PRIMARY KEY,
    community_id      TEXT REFERENCES dim_community(community_id),
    created_date      DATE,
    work_order_type   TEXT,
    ai_triaged        INTEGER,
    triage_minutes    REAL,
    truck_roll        INTEGER,
    resolved_remotely INTEGER,
    repeat_within_30d INTEGER                 -- the telecom equivalent of a 30-day readmission
);

CREATE TABLE ref_competitor_profile (
    provider TEXT, headquarters TEXT, founded TEXT, ownership TEXT, footprint TEXT,
    markets TEXT, business_model TEXT, notable_differentiators TEXT, source_url TEXT
);

CREATE INDEX ix_wo_comm_date ON fact_work_orders (community_id, created_date);
