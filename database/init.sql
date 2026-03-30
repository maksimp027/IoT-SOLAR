CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for stations
CREATE TABLE IF NOT EXISTS dim_stations (
    station_id UUID PRIMARY KEY,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    base_power_kw FLOAT NOT NULL,
    installation_date TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Partitioned table for raw telemetry
CREATE TABLE IF NOT EXISTS fact_raw_telemetry (
    station_id UUID REFERENCES dim_stations(station_id),
    timestamp TIMESTAMP NOT NULL,
    power_output_w FLOAT NOT NULL CHECK (power_output_w >= 0),
    temperature_c FLOAT NOT NULL,
    cloud_cover_pct FLOAT NOT NULL CHECK (cloud_cover_pct >= 0 AND cloud_cover_pct <= 1),
    PRIMARY KEY (station_id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Default partition
CREATE TABLE fact_raw_telemetry_default PARTITION OF fact_raw_telemetry DEFAULT;

-- View for 15-minute statistics (ELT)
CREATE OR REPLACE VIEW mart_15min_stats AS
SELECT
    station_id,
    date_trunc('hour', timestamp) + floor(extract(minute from timestamp) / 15) * interval '15 min' as period_start,
    AVG(power_output_w) as avg_power_w,
    SUM(power_output_w * 15 / 60) / 1000 as generated_kwh,
    MAX(temperature_c) as peak_temperature_c
FROM fact_raw_telemetry
GROUP BY station_id, period_start;

-- Analytical Views for Advanced Reporting (Window Functions & Tracking Anomalies)
CREATE OR REPLACE VIEW vw_power_anomalies AS
WITH rolling_stats AS (
    SELECT
        station_id,
        period_start as time_bucket,
        avg_power_w,
        AVG(avg_power_w) OVER (
            PARTITION BY station_id
            ORDER BY period_start
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
        ) as rolling_avg_power,
        STDDEV(avg_power_w) OVER (
            PARTITION BY station_id
            ORDER BY period_start
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
        ) as rolling_stddev
    FROM mart_15min_stats
)
SELECT
    station_id,
    time_bucket,
    avg_power_w,
    rolling_avg_power,
    ROUND(((avg_power_w - rolling_avg_power) / NULLIF(rolling_stddev, 0))::numeric, 2) as z_score
FROM rolling_stats
WHERE ABS((avg_power_w - rolling_avg_power) / NULLIF(rolling_stddev, 0)) > 2.5;

CREATE OR REPLACE VIEW vw_daily_efficiency AS
SELECT
    station_id,
    DATE(period_start) as stats_date,
    SUM(avg_power_w) as actual_power_daily,
    (SUM(avg_power_w) / 500.0) as theoretical_efficiency_ratio
FROM mart_15min_stats
GROUP BY 1, 2;
