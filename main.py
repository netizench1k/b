from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db, engine, Base
import requests

# ====== МОДЕЛИ PYDANTIC ======
class UserCreate(BaseModel):
    tg_id: int
    tg_username: Optional[str] = None
    first_name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    tg_id: int
    tg_username: Optional[str]
    first_name: str
    rating: float
    
    class Config:
        from_attributes = True

class TripCreate(BaseModel):
    trip_type: str  # "from_campus" или "to_campus"
    point: str
    point_lat: Optional[float] = None
    point_lon: Optional[float] = None
    departure_time: datetime
    seats_total: int = Field(ge=1, le=8)
    price: int = Field(ge=0)
    comment: Optional[str] = None
    max_deviation_km: int = Field(default=3, ge=0, le=20)

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
    created_at: datetime
    driver: UserResponse
    
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
    status: str  # "confirmed" или "rejected"

# ====== LIFESPAN ИНИЦИАЛИЗАЦИЯ БАЗЫ ======
@asynccontextmanager
async def lifespan(app_: FastAPI):
    """Инициализация при запуске"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных инициализирована")
    yield

# ====== СОЗДАНИЕ ПРИЛОЖЕНИЯ ======
app = FastAPI(title="DVFU Ride API", lifespan=lifespan)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== API ЭНДПОИНТЫ ======

# ----- ПОЛЬЗОВАТЕЛИ -----
@app.post("/api/users", response_model=UserResponse)
async def create_or_get_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать или получить пользователя"""
    user = await requests.get_or_create_user(
        db,
        tg_id=user_data.tg_id,
        tg_username=user_data.tg_username,
        first_name=user_data.first_name
    )
    return user

# ----- ПОЕЗДКИ -----
@app.post("/api/trips", response_model=TripResponse)
async def create_new_trip(
    trip_data: TripCreate,
    driver_tg_id: int = Query(..., description="Telegram ID водителя"),
    db: AsyncSession = Depends(get_db)
):
    """Создать новую поездку"""
    # Получаем или создаём пользователя
    driver = await requests.get_or_create_user(db, driver_tg_id)
    
    # Создаём поездку
    trip = await requests.create_trip(
        db=db,
        driver_id=driver.id,
        trip_type=trip_data.trip_type,
        point=trip_data.point,
        point_lat=trip_data.point_lat,
        point_lon=trip_data.point_lon,
        departure_time=trip_data.departure_time,
        seats_total=trip_data.seats_total,
        price=trip_data.price,
        comment=trip_data.comment,
        max_deviation_km=trip_data.max_deviation_km
    )
    
    # Загружаем данные водителя
    await db.refresh(trip, ["driver"])
    return trip

@app.get("/api/trips", response_model=List[TripResponse])
async def get_trips(
    trip_type: Optional[str] = Query(None, description="Тип поездки: from_campus или to_campus"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Получить список активных поездок"""
    trips = await requests.get_active_trips(db, trip_type, limit, offset)
    return trips

@app.get("/api/trips/{trip_id}", response_model=TripResponse)
async def get_trip_details(
    trip_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить детали поездки"""
    trip = await requests.get_trip_with_details(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    return trip

@app.get("/api/trips/nearby", response_model=List[TripResponse])
async def find_nearby_trips(
    lat: float = Query(..., description="Широта"),
    lon: float = Query(..., description="Долгота"),
    trip_type: str = Query(..., description="Тип поездки"),
    max_distance_km: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Найти поездки рядом с указанной точкой"""
    trips = await requests.find_trips_near_location(
        db, lat, lon, trip_type, max_distance_km
    )
    return trips

# ----- БРОНИРОВАНИЯ -----
@app.post("/api/trips/{trip_id}/book", response_model=BookingResponse)
async def book_trip(
    trip_id: int,
    booking_data: BookingCreate,
    passenger_tg_id: int = Query(..., description="Telegram ID пассажира"),
    db: AsyncSession = Depends(get_db)
):
    """Забронировать место в поездке"""
    # Получаем или создаём пользователя
    passenger = await requests.get_or_create_user(db, passenger_tg_id)
    
    try:
        booking = await requests.create_booking(
            db=db,
            trip_id=trip_id,
            passenger_id=passenger.id,
            passenger_lat=booking_data.passenger_lat,
            passenger_lon=booking_data.passenger_lon
        )
        return booking
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/bookings/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    update_data: BookingUpdate,
    driver_tg_id: int = Query(..., description="Telegram ID водителя"),
    db: AsyncSession = Depends(get_db)
):
    """Обновить статус бронирования (только для водителя)"""
    # Получаем водителя
    driver = await requests.get_or_create_user(db, driver_tg_id)
    
    try:
        booking = await requests.update_booking_status(
            db=db,
            booking_id=booking_id,
            driver_id=driver.id,
            new_status=update_data.status
        )
        return booking
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/users/{tg_id}/trips")
async def get_user_trips(
    tg_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить поездки пользователя (как водителя и как пассажира)"""
    # Получаем пользователя
    user = await requests.get_or_create_user(db, tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Поездки как водителя
    driver_trips = await db.execute(
        select(requests.Trip)
        .where(requests.Trip.driver_id == user.id)
        .order_by(requests.Trip.departure_time.desc())
    )
    from sqlalchemy.orm import selectinload
    # Бронирования как пассажира
    passenger_bookings = await db.execute(
        select(requests.Booking)
        .where(requests.Booking.passenger_id == user.id)
        .options(selectinload(requests.Booking.trip).selectinload(requests.Trip.driver))
        .order_by(requests.Booking.created_at.desc())
    )
    
    return {
        "as_driver": driver_trips.scalars().all(),
        "as_passenger": passenger_bookings.scalars().all()
    }

# ====== ЗАПУСК СЕРВЕРА ======
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)