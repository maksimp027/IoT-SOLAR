# Analytics Showcase: Advanced SQL & Statistical Modeling

This document highlights the core data engineering and analytical methodologies implemented in the **Solar IoT Analytics** project. The architecture is deliberately designed around modern Analytics Engineering principles, **shifting heavy transformations to the database layer (ELT)** and leveraging applied statistics for predictive maintenance, rather than relying solely on application-layer logic.

## 1. Database-Centric ELT (Extract, Load, Transform)

### Why PostgreSQL over Pandas?
In IoT scenarios, telemetry data accumulates rapidly, generating millions of rows daily. Processing this raw data in memory using Python (Pandas) becomes a massive bottleneck, requiring constant data movement and heavy compute instances. Instead, this project employs a **database-centric ELT approach**:

* **Partitioning:** The `fact_raw_telemetry` table is partitioned by time, ensuring fast writes and efficient pruning during queries.
* **In-Database Aggregations:** Raw data is immediately modeled into the `mart_15min_stats` view (acting as our data mart).

### The Business Logic of 15-Minute Windows
Power grid dispatchers and energy markets typically operate in 15-minute or hourly trading intervals. By using `date_trunc` and modulo arithmetic on the database side, the chaotic, high-frequency raw telemetry is collapsed into consistent 15-minute intervals. We calculate the `avg_power_w` and the true energy generated (`generated_kwh` mathematically integrated using power and time). This reduces data volume by orders of magnitude while preserving 100% of the analytical value.

---
## 2. Advanced SQL: Anomaly Detection

To detect anomalies effectively without spinning up external machine learning services, I heavily utilize PostgreSQL's **Window Functions**. This allows for complex row-to-row comparisons, time-series smoothing, and statistical anomaly detection directly within the query engine.

### Query 1: Detecting "Shadow Anomalies" (Peer-to-Peer Comparative Drop)
Often, a drop in power is just a cloud passing by. But if one station drops by 20% while the rest of the fleet maintains high output, it's a localized anomaly (e.g., equipment failure, heavy local shading, or debris).

```sql
WITH network_stats AS (
    SELECT 
        period_start, 
        AVG(avg_power_w) as network_avg_power 
    FROM mart_15min_stats 
    GROUP BY period_start
), 
station_comparison AS (
    SELECT 
        m.station_id, 
        m.period_start, 
        m.avg_power_w as station_power, 
        n.network_avg_power, 
        (m.avg_power_w - n.network_avg_power) / NULLIF(n.network_avg_power, 0) as deviation_from_network 
    FROM mart_15min_stats m 
    JOIN network_stats n ON m.period_start = n.period_start
) 
SELECT 
    station_id, 
    period_start, 
    ROUND(station_power::numeric, 2) as station_power, 
    ROUND(network_avg_power::numeric, 2) as network_avg_power, 
    ROUND((deviation_from_network * 100)::numeric, 2) as deviation_pct 
FROM station_comparison 
WHERE deviation_from_network <= -0.20; -- Dropped 20% below fleet average
```

### Query 2: Rolling Average Efficiency (7-Day Smoothing)
Solar efficiency fluctuates wildly due to daily weather. To evaluate true hardware degradation, we must calculate a smoothed rolling average of efficiency over a 7-day window.

```sql
WITH daily_efficiency AS (
    SELECT 
        station_id, 
        DATE(period_start) as stats_date, 
        SUM(avg_power_w) / 5000.0 as daily_theoretical_ratio 
    FROM mart_15min_stats 
    GROUP BY station_id, DATE(period_start)
) 
SELECT 
    station_id, 
    stats_date, 
    ROUND(daily_theoretical_ratio::numeric, 4) as daily_ratio,
    ROUND(AVG(daily_theoretical_ratio) OVER (
        PARTITION BY station_id 
        ORDER BY stats_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    )::numeric, 4) as rolling_7d_efficiency 
FROM daily_efficiency;
```

---

## 3. Applied Statistics: The Bayesian Approach

Beyond simple thresholds, the `engine.py` orchestrates a mathematically rigorous anomaly detection system for panel degradation.

### The Physics Model as the "Prior"
In `station.py`, the system calculates the astronomical elevation angle of the sun, adjusting for dynamic cloud cover and thermal losses (gamma = 0.4% per °C). This theoretical maximum formulation represents our **Bayesian Prior** — the scientifically expected energy yield.

### Database Aggregations as the "Likelihood"
The `mart_15min_stats` serves as our factual observations (the Likelihood). The physical world is noisy (dust, micro-shading), so the actual output rarely matches the perfect physical equation.

### Bayesian Updating for Predictive Maintenance
By continuously comparing the **Prior** (Physical Model) against the **Likelihood** (Database Facts), we calculate the posterior belief of the health of the panel. If the probability distribution of the actual output statistically shifts to the left of the expected distribution (measured over days, not minutes), the system confirms a structural degradation rather than a fleeting weather event. This triggers predictive maintenance alerts before total failure occurs.

---

## 4. Enterprise BI Integration (Agnostic Architecture)

A robust Data Engineering architecture shouldn't be locked into a single visualization layer. Because the heavy lifting is handled by ELT processes within PostgreSQL, the `mart_15min_stats` and the advanced analytical views act as a **Single Source of Truth (SSOT)**.

Data Analysts and BI Developers can seamlessly connect enterprise tools like **Tableau**, **Power BI**, **Looker**, or **Grafana** directly to the PostgreSQL instance. They can instantly visualize rolling averages, heatmaps, and anomalies without writing complex DAX/Calculated fields or processing millions of raw telemetry rows. The database serves curated, query-optimized data marts ready for enterprise consumption.