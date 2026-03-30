# Solar IoT Analytics & Forecasting

![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![SciPy](https://img.shields.io/badge/SciPy-%230C55A5.svg?style=for-the-badge&logo=scipy&logoColor=%white)
![Chart.js](https://img.shields.io/badge/chart.js-F5788D.svg?style=for-the-badge&logo=chart.js&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

An End-to-End Data Analytics and Engineering project showcasing advanced ELT pipelines, Time-Series data warehousing, and Statistical automated forecasting for Solar Power Plants.

## Business Value
This platform ensures operational efficiency of solar power plants by transforming raw sensor telemetry into actionable insights:
- **Anomaly Detection**: Real-time monitoring of unexpected power drops using statistical Z-scores (Window Functions).
- **Performance Degradation Heatmaps**: Visualizes energy grid efficiency vs theoretical maximums, helping direct maintenance teams exactly where they are needed.
- **Predictive Yield Forecasts**: Uses Bayesian inference to forecast solar generation for the next 72 hours, optimizing energy grid dispatch.

## The Data Pipeline Architecture

1. **Physics Generator (The Source)**: High-throughput asynchronous emulator (`emulator/runner.py`) simulating realistic solar telemetry (including variations for cloud cover and temperature).
2. **Data Quality Gate (Ingestion)**: High-concurrency FastAPI entry-points utilizing Pydantic for strict schema validation.
3. **Time-Series DWH (Storage)**: PostgreSQL database specifically tuned for hyper-dimensional time-series data. 
4. **ELT Transformations**: In-database transformations aggregating raw massive fact tables into targeted 15-minute dimensional data marts.
5. **Statistical Forecast (Analytics)**: `analytics/engine.py` applies Gaussian probability distributions to contrast prior expectations (ideal conditions) against posterior facts (database aggregation), identifying hardware degradation.

---

## Quick Start

### 1. Start the Data Warehouse
```bash
docker-compose up -d
```

### 2. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Generate Telemetry Data
```bash
python emulator/runner.py
```

### 4. Launch Analytics API
```bash
cd gateway
uvicorn main:app --reload --port 8000
```
Open `solar_iot_dashboard.html` in your browser to observe the real-time analytics!

---

## Live UI Preview

Don't want to set up the database and backend?  
**[Open `preview.html` in your browser](https://maksimp027.github.io/IoT-SOLAR/preview.html)** to explore the interactive UI populated with static mock data.

---

*Developed as a Data Analyst / Analytics Engineer portfolio project.*
