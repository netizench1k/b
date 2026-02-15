from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import schemas, crud, geo, models
from database import get_db
from typing import List, Optional
from datetime import datetime

router = APIRouter(tags=["trips"])

@router.post("/trips", response_model=schemas.TripResponse)
async def create_trip(
    trip_data: schemas.TripCreate,
    driver_tg_id: int = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. Получить/создать пользователя
    user = await crud.get_or_create_user(db, driver_tg_id)
    
    # 2. Геокодировать адрес
    lat, lon, formatted = await geo.geocode_address(trip_data.point, db)
    
    # 3. Создать поездку
    trip = models.Trip(
        driver_id=user.id,
        trip_type=trip_data.trip_type,
        point=formatted,
        point_lat=lat,
        point_lon=lon,
        departure_time=trip_data.departure_time,
        seats_total=trip_data.seats_total,
        seats_available=trip_data.seats_total,
        price=trip_data.price,
        comment=trip_data.comment,
        max_deviation_km=trip_data.max_deviation_km,
        time_flexibility_minutes=trip_data.time_flexibility_minutes,
        status="active"
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    await db.refresh(trip, ["driver"])
    return trip

@router.get("/search", response_model=List[schemas.TripResponse])
async def search_trips(
    trip_type: str = Query(...),
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    max_distance_km: int = 5,
    max_deviation_minutes: int = 30,
    time_from: Optional[datetime] = None,
    time_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Поиск поездок с гео-рекомендациями"""
    # Если передан адрес, геокодируем
    if address:
        lat, lon, _ = await geo.geocode_address(address, db)
    elif lat is None or lon is None:
        raise HTTPException(400, "Укажите адрес или координаты")
    
    trips = await crud.get_nearby_trips(
        db, lat, lon, trip_type, max_distance_km, max_deviation_minutes,
        time_from, time_to
    )
    return trips

@router.get("/{trip_id}", response_model=schemas.TripResponse)
async def get_trip(trip_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Trip)
        .where(models.Trip.id == trip_id)
        .options(selectinload(models.Trip.driver))
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(404)
    return trip

@router.post("/{trip_id}/book", response_model=schemas.BookingResponse)
async def book_trip(
    trip_id: int,
    booking_data: schemas.BookingCreate,
    passenger_tg_id: int = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # Получить пассажира
    passenger = await crud.get_or_create_user(db, passenger_tg_id)
    # Проверить поездку
    trip_result = await db.execute(
        select(models.Trip).where(models.Trip.id == trip_id, models.Trip.status == "active")
    )
    trip = trip_result.scalar_one_or_none()
    if not trip:
        raise HTTPException(404, "Поездка не найдена")
    if trip.seats_available <= 0:
        raise HTTPException(400, "Нет мест")
    
    # Проверить дубликат
    existing = await db.execute(
        select(models.Booking).where(
            models.Booking.trip_id == trip_id,
            models.Booking.passenger_id == passenger.id,
            models.Booking.status.in_(["pending", "confirmed"])
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Вы уже забронировали")
    
    booking = models.Booking(
        trip_id=trip_id,
        passenger_id=passenger.id,
        passenger_lat=booking_data.passenger_lat,
        passenger_lon=booking_data.passenger_lon,
        status="pending"
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking