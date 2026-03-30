import asyncio
import httpx
from datetime import datetime, timedelta
import uuid
import math
from station import SolarStation
import numpy as np

API_URL = "http://localhost:8000/api/v1"

async def fast_stream(stations, hours_back=24):
    async with httpx.AsyncClient() as client:
        # Register all stations
        for st in stations:
            await client.post(f"{API_URL}/stations", json={
                "station_id": str(st.station_id),
                "latitude": st.latitude,
                "longitude": st.longitude,
                "base_power_kw": st.base_power_kw
            })
        print(f"Registered {len(stations)} stations. Batch-loading past data...")

        now = datetime.now()
        start_time = now - timedelta(hours=hours_back)
        start_time = start_time.replace(minute=0, second=0, microsecond=0)

        current_time = start_time
        batch = []

        # 1. BATCH MODE (Fill history instantly)
        while current_time <= now:
            for st in stations:
                temperature = 15.0 + 10 * math.sin(math.pi * (current_time.hour - 6) / 12)
                cloud_cover = np.random.uniform(0.1, 0.4)

                # Add shadow anomaly for Station 4 (index 3) at 14:00 to test Dashboard Heatmap
                if stations.index(st) == 3 and current_time.hour == 14:
                    cloud_cover = 0.95

                p_out = st.generate_reading(current_time, temperature, cloud_cover)

                batch.append({
                    "station_id": str(st.station_id),
                    "timestamp": current_time.isoformat(),
                    "power_output_w": round(p_out, 2),
                    "temperature_c": round(temperature, 2),
                    "cloud_cover_pct": round(cloud_cover, 2)
                })

            # Send chunks of 200 to avoid large payload drop
            if len(batch) >= 200:
                await client.post(f"{API_URL}/telemetry/batch", json=batch)
                batch = []

            current_time += timedelta(minutes=15)

        if batch:
            await client.post(f"{API_URL}/telemetry/batch", json=batch)

        print(f"Success! Loaded {hours_back} hours of historical 15-minute telemetry into DWH.")
        print("Entering HYPER-STREAM mode (1 tick = 15 minutes, sending every 1 second)")

        # 2. HYPER-STREAM MODE (Fast forwarding the future)
        while True:
            current_time += timedelta(minutes=15)
            batch = []
            for st in stations:
                temperature = 15.0 + 10 * math.sin(math.pi * (current_time.hour - 6) / 12)
                cloud_cover = np.random.uniform(0.1, 0.4)
                p_out = st.generate_reading(current_time, temperature, cloud_cover)

                batch.append({
                    "station_id": str(st.station_id),
                    "timestamp": current_time.isoformat(),
                    "power_output_w": round(p_out, 2),
                    "temperature_c": round(temperature, 2),
                    "cloud_cover_pct": round(cloud_cover, 2)
                })

            res = await client.post(f"{API_URL}/telemetry/batch", json=batch)
            print(f"[{current_time.strftime('%H:%M:%S')}] Forwarded +15min interval for 12 units. Status: {res.status_code}")

            await asyncio.sleep(1.0) # wait only 1 second in real life!

if __name__ == "__main__":
    # Generate exactly 12 stations to perfectly fill our 12_ACTIVE_UNITS dashboard UI
    stations = []
    for i in range(12):
        st_id = uuid.uuid4()
        lat = 50.45 + (i * 0.02)
        lon = 30.52 + (i * 0.02)
        stations.append(SolarStation(st_id, latitude=lat, longitude=lon, base_power_kw=1.0))

    asyncio.run(fast_stream(stations, hours_back=48))
