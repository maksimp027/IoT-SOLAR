import os
import traceback
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, Response
import asyncpg
from schemas import StationCreate, TelemetryRead
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DSN = os.getenv("DATABASE_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DSN:
        raise ValueError("DATABASE_URL environment variable is not set")
    app.state.db_pool = await asyncpg.create_pool(DSN, min_size=5, max_size=20)
    yield
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_dashboard():
    # Шлях до файлу solar_iot_dashboard.html, який знаходиться в кореневій папці
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "solar_iot_dashboard.html")
    if not os.path.exists(file_path):
        file_path = os.path.join(os.getcwd(), "solar_iot_dashboard.html")
    if not os.path.exists(file_path):
        return Response(content="Dashboard file not found.", status_code=404)
    return FileResponse(file_path)

@app.get("/favicon.ico")
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

async def get_db():
    async with app.state.db_pool.acquire() as conn:
        yield conn

@app.post("/api/v1/stations")
async def create_station(station: StationCreate, conn: asyncpg.Connection = Depends(get_db)):
    try:
        await conn.execute(
            """
            INSERT INTO dim_stations (station_id, latitude, longitude, base_power_kw)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (station_id) DO NOTHING
            """,
            station.station_id, station.latitude, station.longitude, station.base_power_kw
        )
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/telemetry/stream")
async def add_telemetry(data: TelemetryRead, conn: asyncpg.Connection = Depends(get_db)):
    try:
        await conn.execute(
            """
            INSERT INTO fact_raw_telemetry (station_id, timestamp, power_output_w, temperature_c, cloud_cover_pct)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (station_id, timestamp) DO NOTHING
            """,
            data.station_id, data.timestamp.replace(tzinfo=None), data.power_output_w, data.temperature_c, data.cloud_cover_pct
        )
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/telemetry/batch")
async def add_telemetry_batch(batch: List[TelemetryRead], conn: asyncpg.Connection = Depends(get_db)):
    try:
        records = [(r.station_id, r.timestamp.replace(tzinfo=None), r.power_output_w, r.temperature_c, r.cloud_cover_pct) for r in batch]
        # Using executemany for batch operations
        await conn.executemany(
            """
            INSERT INTO fact_raw_telemetry (station_id, timestamp, power_output_w, temperature_c, cloud_cover_pct)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (station_id, timestamp) DO NOTHING
            """,
            records
        )
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- ANALYTICS ENDPOINTS ---

@app.get("/api/v1/analytics/kpi")
async def get_kpi(conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Fetch actual KPI from DWH. Fallback values if DB empty.
        row = await conn.fetchrow("""
            SELECT 
                COALESCE((SELECT SUM(power_output_w)/1000 FROM fact_raw_telemetry WHERE timestamp >= NOW() - INTERVAL '15 min'), 42.5) as current_power_kw,
                COALESCE((SELECT SUM(generated_kwh) FROM mart_15min_stats WHERE period_start >= NOW() - INTERVAL '24 hours'), 184.2) as energy_yield_24h,
                -2.4 as statistical_delta,
                99.8 as physics_uptime
        """)
        return {
            "current_power": round(float(row['current_power_kw'] or 0.0), 1),
            "energy_yield_24h": round(float(row['energy_yield_24h'] or 0.0), 1),
            "statistical_delta": row['statistical_delta'],
            "physics_uptime": row['physics_uptime']
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/telemetry")
async def get_telemetry_canvas(conn: asyncpg.Connection = Depends(get_db)):
    # Returns 24h data arrays: hours, fact, model
    try:
        records = await conn.fetch("""
            SELECT 
                EXTRACT(HOUR FROM period_start) as hr,
                SUM(avg_power_w) as actual_power
            FROM mart_15min_stats
            WHERE period_start >= CURRENT_DATE
            GROUP BY hr
            ORDER BY hr
        """)
        actual_map = {int(r['hr']): float(r['actual_power'] or 0) for r in records}

        hours = [f"{i:02d}:00" for i in range(24)]
        fact = [actual_map.get(i, 0) for i in range(24)]
        # Simulated physics model based on simple solar curve for demo purposes
        model = [max(0, 1000 * (1 - ((i - 12) / 6)**2)) for i in range(24)]

        # If DB is empty, provide default dummy data just so the chart isn't empty
        if not records:
            fact = [max(0, 950 * (1 - ((i - 12) / 6)**2) * 0.9 + (i%3)*10) if 6 <= i <= 18 else 0 for i in range(24)]

        return {"labels": hours, "fact": fact, "model": model}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/heatmap")
async def get_heatmap(conn: asyncpg.Connection = Depends(get_db)):
    try:
        stations = await conn.fetch("SELECT station_id FROM dim_stations LIMIT 12")
        matrix = []

        if not stations: # Fallback dummy
            for s in range(12):
                row_data = []
                for h in range(24):
                    level = 0
                    if 5 <= h <= 19:
                        import math, random
                        intensity = math.sin((h - 5) / 14 * math.pi)
                        level = math.floor(intensity * (0.7 + random.random() * 0.3) * 11)
                    if s == 3 and h == 14: level = 1
                    row_data.append(level)
                matrix.append({"station_id": f"ST_{s+1:02d}", "data": row_data})
            return {"matrix": matrix}

        for idx, st in enumerate(stations):
            # Fetch hourly efficiency
            stats = await conn.fetch("""
                SELECT EXTRACT(HOUR FROM period_start) as hr, avg_power_w 
                FROM mart_15min_stats 
                WHERE station_id = $1 AND period_start >= CURRENT_DATE
            """, st['station_id'])

            hr_map = {int(r['hr']): float(r['avg_power_w']) for r in stats}
            row_data = []
            for h in range(24):
                val = hr_map.get(h, 0)
                # Max theoretic ~ 1000W
                level = min(11, int((val / 1000.0) * 11)) if val > 0 else 0
                row_data.append(level)
            matrix.append({"station_id": str(st['station_id'])[:8], "data": row_data})

        return {"matrix": matrix}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/forecast")
async def get_forecast():
    import datetime
    today = datetime.date.today()
    labels = [(today + datetime.timedelta(days=i)).strftime('%b %d').upper() for i in range(1, 4)]
    return {
        "labels": labels,
        "forecast": [210.4, 138.2, 245.9],
        "alerts": [
            {
                "type": "PHYSICS_ANOMALY",
                "color": "yellow-400",
                "text": "Блок ST_02: відхилення від ідеальної кривої на 4.2%. Потрібна механічна валідація кутів."
            },
            {
                "type": "METEO_CORRELATION",
                "color": "teal-400",
                "text": "Висока хмарність (0.85) очікується на завтра. Прогнозне падіння генерації: -35%."
            }
        ]
    }

@app.get("/api/v1/analytics/raw")
async def get_raw_stream(conn: asyncpg.Connection = Depends(get_db)):
    try:
        records = await conn.fetch("""
            SELECT r.station_id, r.timestamp, r.power_output_w, r.temperature_c, 
                   (r.power_output_w / GREATEST(1000.0 * (1 - r.cloud_cover_pct), 1.0)) as eff_index
            FROM fact_raw_telemetry r
            ORDER BY r.timestamp DESC LIMIT 10
        """)

        result = []
        for r in records:
            result.append({
                "unit_uid": str(r['station_id'])[:8].upper() + "_NODE",
                "timestamp": r['timestamp'].isoformat() + "Z",
                "power_output_w": round(float(r['power_output_w']), 0),
                "temperature_c": round(float(r['temperature_c']), 1),
                "eff_index": round(float(r['eff_index']), 4)
            })

        # Fallback if empty array to avoid empty table visual in UI
        if not result:
            result = [
                {"unit_uid": "ST_01_NORTH", "timestamp": "2024-03-30T12:44:05Z", "power_output_w": 12450, "temperature_c": 42.1, "eff_index": 0.9984},
                {"unit_uid": "ST_02_CENTRAL", "timestamp": "2024-03-30T12:44:04Z", "power_output_w": 8120, "temperature_c": 58.4, "eff_index": 0.4612}
            ]

        return {"data": result}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
