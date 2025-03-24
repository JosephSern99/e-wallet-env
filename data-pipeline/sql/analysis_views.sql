-- create_analysis_views.sql
-- Creates useful analytical views for the e-wallet data
-- Transaction volume by day
CREATE OR REPLACE VIEW dw.vw_daily_transaction_volume AS
SELECT dt.year,
    dt.month,
    dt.day,
    COUNT(ft.transaction_id) AS num_transactions,
    SUM(ft.amount) AS total_amount,
    ft.currency,
    ft.transaction_type
FROM dw.fact_transactions ft
    JOIN dw.dim_time dt ON ft.transaction_time = dt.timestamp
WHERE ft.status = 'COMPLETED'
GROUP BY dt.year,
    dt.month,
    dt.day,
    ft.currency,
    ft.transaction_type
ORDER BY dt.year,
    dt.month,
    dt.day;
-- User transaction summary
CREATE OR REPLACE VIEW dw.vw_user_transaction_summary AS
SELECT ft.user_id,
    COUNT(ft.transaction_id) AS total_transactions,
    SUM(
        CASE
            WHEN ft.status = 'COMPLETED' THEN 1
            ELSE 0
        END
    ) AS successful_transactions,
    SUM(
        CASE
            WHEN ft.status = 'FAILED' THEN 1
            ELSE 0
        END
    ) AS failed_transactions,
    SUM(
        CASE
            WHEN ft.is_flagged = TRUE THEN 1
            ELSE 0
        END
    ) AS flagged_transactions,
    SUM(ft.amount) AS total_amount,
    MAX(ft.transaction_time) AS latest_transaction,
    MIN(ft.transaction_time) AS first_transaction
FROM dw.fact_transactions ft
GROUP BY ft.user_id;
-- Transaction category analysis
CREATE OR REPLACE VIEW dw.vw_category_analysis AS
SELECT COALESCE(ft.category, 'UNCATEGORIZED') AS category,
    COUNT(ft.transaction_id) AS num_transactions,
    SUM(ft.amount) AS total_amount,
    AVG(ft.amount) AS avg_amount,
    MIN(ft.amount) AS min_amount,
    MAX(ft.amount) AS max_amount,
    dt.year,
    dt.month
FROM dw.fact_transactions ft
    JOIN dw.dim_time dt ON ft.transaction_time = dt.timestamp
WHERE ft.status = 'COMPLETED'
GROUP BY COALESCE(ft.category, 'UNCATEGORIZED'),
    dt.year,
    dt.month
ORDER BY dt.year,
    dt.month,
    total_amount DESC;
-- Hourly transaction patterns
CREATE OR REPLACE VIEW dw.vw_hourly_patterns AS
SELECT dt.hour,
    COUNT(ft.transaction_id) AS num_transactions,
    SUM(ft.amount) AS total_amount,
    AVG(ft.amount) AS avg_transaction_size,
    dt.is_weekend
FROM dw.fact_transactions ft
    JOIN dw.dim_time dt ON ft.transaction_time = dt.timestamp
WHERE ft.status = 'COMPLETED'
GROUP BY dt.hour,
    dt.is_weekend
ORDER BY dt.hour;
-- Geographic transaction distribution
CREATE OR REPLACE VIEW dw.vw_geographic_distribution AS
SELECT ROUND(ft.latitude, 1) AS lat_rounded,
    ROUND(ft.longitude, 1) AS lng_rounded,
    COUNT(ft.transaction_id) AS num_transactions,
    SUM(ft.amount) AS total_amount,
    AVG(ft.amount) AS avg_amount
FROM dw.fact_transactions ft
WHERE ft.latitude IS NOT NULL
    AND ft.longitude IS NOT NULL
    AND ft.status = 'COMPLETED'
GROUP BY ROUND(ft.latitude, 1),
    ROUND(ft.longitude, 1)
ORDER BY num_transactions DESC;
-- Flagged transactions analysis
CREATE OR REPLACE VIEW dw.vw_flagged_transactions AS
SELECT dt.year,
    dt.month,
    dt.day,
    COUNT(ft.transaction_id) AS flagged_count,
    SUM(ft.amount) AS flagged_amount,
    ft.transaction_type