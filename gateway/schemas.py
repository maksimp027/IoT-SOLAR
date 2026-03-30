from pydantic import BaseModel, conint
from pydantic.fields import Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class StationCreate(BaseModel):
    station_id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    base_power_kw: float = Field(gt=0)
    installation_date: Optional[datetime] = None

class TelemetryRead(BaseModel):
    station_id: UUID
    timestamp: datetime
    power_output_w: float = Field(ge=0)
    temperature_c: float = Field(ge=-50, le=80)
    cloud_cover_pct: float = Field(ge=0.0, le=1.0)

