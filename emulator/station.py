import math
import numpy as np
from datetime import datetime

class SolarStation:
    def __init__(self, station_id, latitude, longitude, base_power_kw, installation_date=None):
        self.station_id = station_id
        self.latitude = latitude
        self.longitude = longitude
        self.base_power_kw = base_power_kw
        self.installation_date = installation_date or datetime.now()

    def _calculate_solar_angle(self, dt: datetime):
        # A simple approximation of solar elevation angle
        day_of_year = dt.timetuple().tm_yday
        hour = dt.hour + dt.minute / 60.0

        # Declination angle
        declination = 23.45 * math.sin(math.radians(360.0 * (284 + day_of_year) / 365.0))

        # Hour angle
        hour_angle = 15.0 * (hour - 12.0)

        # Elevation angle
        sin_elevation = (math.sin(math.radians(self.latitude)) * math.sin(math.radians(declination)) +
                         math.cos(math.radians(self.latitude)) * math.cos(math.radians(declination)) * math.cos(math.radians(hour_angle)))

        elevation = math.degrees(math.asin(sin_elevation))
        return max(0.0, elevation)

    def generate_reading(self, dt: datetime, temperature_c: float, cloud_cover_pct: float, degradation_pct: float=0.0) -> float:
        alpha = self._calculate_solar_angle(dt)

        if alpha <= 0.0:
            return 0.0

        c = cloud_cover_pct
        gamma = 0.004
        T = temperature_c
        d = degradation_pct

        p_base = self.base_power_kw * 1000.0 # to Watts
        sin_alpha = math.sin(math.radians(alpha))

        p_out = p_base * max(0.0, sin_alpha) * (1.0 - c) * (1.0 - gamma * (T - 25.0)) * (1.0 - d)

        # Add random noise for realism (e.g. 1% std)
        noise = np.random.normal(0.0, 0.01 * p_out)
        p_out += noise

        return max(0.0, p_out)

