from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from models import User, Trip, Booking
from datetime import datetime
from typing import List, Optional

# ====== ПОЛЬЗОВАТЕЛИ ======
async def get_or_create_user(
    db: AsyncSession, 
    tg_id: int, 
    tg_username: str = None, 
    first_name: str = None
) -> User:
    """Получаем пользователя или создаём нового"""
    result = await db.execute(
        select(User).where(User.tg_id == tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            tg_id=tg_id,
            tg_username=tg_username,
            first_name=first_name
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user

# ====== ПОЕЗДКИ ======
async def create_trip(
    db: AsyncSession,
    driver_id: int,
    trip_type: str,
    point: str,
    point_lat: Optional[float],
    point_lon: Optional[float],
    departure_time: datetime,
    seats_total: int,
    price: int,
    comment: Optional[str] = None,
    max_deviation_km: int = 3
) -> Trip:
    """Создание новой поездки"""
    trip = Trip(
        driver_id=driver_id,
        trip_type=trip_type,
        point=point,
        point_lat=point_lat,
        point_lon=point_lon,
        departure_time=departure_time,
        seats_total=seats_total,
        seats_available=seats_total,
        price=price,
        comment=comment,
        max_deviation_km=max_deviation_km,
        status="active"
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return trip

async def get_active_trips(
    db: AsyncSession,
    trip_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Trip]:
    """Получение активных поездок с фильтрацией"""
    query = select(Trip).where(Trip.status == "active")
    
    if trip_type:
        query = query.where(Trip.trip_type == trip_type)
    
    # Показываем сначала ближайшие по времени
    query = query.order_by(Trip.departure_time).limit(limit).offset(offset)
    
    result = await db.execute(query.options(selectinload(Trip.driver)))
    return result.scalars().all()

async def get_trip_with_details(db: AsyncSession, trip_id: int) -> Optional[Trip]:
    """Получение поездки со всеми деталями"""
    result = await db.execute(
        select(Trip)
        .where(Trip.id == trip_id)
        .options(
            selectinload(Trip.driver),
            selectinload(Trip.bookings).selectinload(Booking.passenger)
        )
    )
    return result.scalar_one_or_none()

# ====== БРОНИРОВАНИЯ ======
async def create_booking(
    db: AsyncSession,
    trip_id: int,
    passenger_id: int,
    passenger_lat: Optional[float] = None,
    passenger_lon: Optional[float] = None
) -> Booking:
    """Создание заявки на бронирование"""
    # Проверяем, есть ли свободные места
    trip_result = await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.status == "active")
    )
    trip = trip_result.scalar_one_or_none()
    
    if not trip or trip.seats_available <= 0:
        raise ValueError("Поездка не найдена или нет свободных мест")
    
    # Проверяем, не создавал ли уже пассажир заявку
    existing_booking = await db.execute(
        select(Booking).where(
            Booking.trip_id == trip_id,
            Booking.passenger_id == passenger_id,
            Booking.status.in_(["pending", "confirmed"])
        )
    )
    if existing_booking.scalar_one_or_none():
        raise ValueError("Вы уже подали заявку на эту поездку")
    
    # Создаём бронирование
    booking = Booking(
        trip_id=trip_id,
        passenger_id=passenger_id,
        passenger_lat=passenger_lat,
        passenger_lon=passenger_lon,
        status="pending"
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking

async def update_booking_status(
    db: AsyncSession,
    booking_id: int,
    driver_id: int,
    new_status: str  # "confirmed" или "rejected"
) -> Booking:
    """Обновление статуса бронирования (только водитель)"""
    # Получаем бронирование с поездкой
    result = await db.execute(
        select(Booking)
        .join(Trip)
        .where(
            Booking.id == booking_id,
            Trip.driver_id == driver_id  # Только водитель может менять статус
        )
        .options(selectinload(Booking.trip))
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise ValueError("Бронирование не найдено или у вас нет прав")
    
    if booking.status != "pending":
        raise ValueError("Статус уже изменен")
    
    # Обновляем статус
    booking.status = new_status
    
    if new_status == "confirmed":
        # Уменьшаем количество свободных мест
        booking.trip.seats_available -= 1
        
        # Если места закончились, меняем статус поездки
        if booking.trip.seats_available <= 0:
            booking.trip.status = "filled"
    
    await db.commit()
    await db.refresh(booking)
    return booking

# ====== ПОИСК ПО ГЕОЛОКАЦИИ ======
async def find_trips_near_location(
    db: AsyncSession,
    lat: float,
    lon: float,
    trip_type: str,
    max_distance_km: int = 5,
    limit: int = 20
) -> List[Trip]:
    """Поиск поездок рядом с указанной точкой"""
    # В SQLite нет PostGIS, поэтому делаем простой радиусный поиск
    # Для продакшена нужно использовать PostGIS
    query = select(Trip).where(
        Trip.status == "active",
        Trip.trip_type == trip_type
    )
    
    result = await db.execute(query.options(selectinload(Trip.driver)))
    trips = result.scalars().all()
    
    # Фильтруем по расстоянию (упрощённый вариант)
    filtered_trips = []
    for trip in trips:
        if trip.point_lat and trip.point_lon:
            # Простая формула расстояния (для небольших расстояний)
            distance_km = ((trip.point_lat - lat) ** 2 + (trip.point_lon - lon) ** 2) ** 0.5 * 111
            if distance_km <= max_distance_km:
                trip.distance_km = round(distance_km, 1)
                filtered_trips.append(trip)
    
    # Сортируем по расстоянию и времени
    filtered_trips.sort(key=lambda x: (x.distance_km, x.departure_time))
    return filtered_trips[:limit]