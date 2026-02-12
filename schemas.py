from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class UserBase(BaseModel):
    tg_id: int
    tg_username: Optional[str] = None
    first_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    rating: float
    class Config:
        from_attributes = True

class TripCreate(BaseModel):
    trip_type: str
    point: str
    departure_time: datetime
    seats_total: int = Field(ge=1, le=8)
    price: int = Field(ge=0)
    comment: Optional[str] = None
    max_deviation_km: int = 3
    time_flexibility_minutes: int = 30

class TripResponse(BaseModel):
    id: int
    trip_type: str
    point: str
    point_lat: Optional[float]
    point_lon: Optional[float]
    departure_time: datetime
    seats_total: int
    seats_available: int
    price: int
    comment: Optional[str]
    status: str
    max_deviation_km: int
    time_flexibility_minutes: int
    created_at: datetime
    driver: UserResponse
    distance_km: Optional[float] = None   # для поиска
    deviation_minutes: Optional[int] = None  # отклонение по времени маршрута
    class Config:
        from_attributes = True

class BookingCreate(BaseModel):
    passenger_lat: Optional[float] = None
    passenger_lon: Optional[float] = None

class BookingResponse(BaseModel):
    id: int
    trip_id: int
    passenger_id: int
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class BookingUpdate(BaseModel):
    status: str

class DriverLocationSchema(BaseModel):
    trip_id: int
    lat: float
    lon: float

class SearchQuery(BaseModel):
    trip_type: str
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    max_distance_km: int = 5
    max_deviation_minutes: int = 30
    time_from: Optional[datetime] = None
    time_to: Optional[datetime] = None