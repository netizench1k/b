from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from models import Trip, User, Booking
from geo import haversine, get_route
from datetime import datetime
from typing import List, Optional

# ----- ПОЛЬЗОВАТЕЛИ -----
async def get_or_create_user(db: AsyncSession, tg_id: int, tg_username: str = None, first_name: str = None) -> User:
    result = await db.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(tg_id=tg_id, tg_username=tg_username, first_name=first_name)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

async def get_active_trips(db: AsyncSession, limit: int = 20, offset: int = 0):
    result = await db.execute(
        select(models.Trip)
        .where(models.Trip.status == "active")
        .order_by(models.Trip.departure_time)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()

async def get_nearby_trips(
    db: AsyncSession,
    lat: float,
    lon: float,
    trip_type: str,
    max_distance_km: int = 5,
    max_deviation_minutes: int = 30,
    time_from: Optional[datetime] = None,
    time_to: Optional[datetime] = None
) -> List[Trip]:
    """
    Основной алгоритм рекомендаций:
    1. Отбираем активные поездки указанного типа.
    2. Вычисляем расстояние между точкой пассажира и точкой водителя (или кампусом).
    3. Если поездка типа 'from_campus' — строим маршрут: кампус -> точка пассажира -> точка водителя,
       вычисляем отклонение по времени.
    4. Ранжируем по релевантности (расстояние + отклонение).
    """
    # Базовый запрос
    query = select(Trip).where(
        Trip.status == "active",
        Trip.trip_type == trip_type,
        Trip.seats_available > 0,
        Trip.departure_time >= datetime.now()
    )
    
    if time_from:
        query = query.where(Trip.departure_time >= time_from)
    if time_to:
        query = query.where(Trip.departure_time <= time_to)
    
    result = await db.execute(query)
    all_trips = result.scalars().all()
    
    # Координаты кампуса (фиксированные)
    CAMPUS_LAT, CAMPUS_LON = 43.0245, 131.8927  # ДВФУ
    
    enriched_trips = []
    for trip in all_trips:
        # Расстояние до точки назначения по прямой
        if trip.point_lat and trip.point_lon:
            distance = haversine(lat, lon, trip.point_lat, trip.point_lon)
        else:
            distance = float('inf')
        
        if distance > max_distance_km:
            continue
        
        # Рассчитываем отклонение маршрута, если поездка ИЗ кампуса
        deviation_minutes = 0
        if trip_type == "from_campus":
            # Время прямого маршрута: кампус -> точка водителя
            _, duration_direct, _ = await get_route(CAMPUS_LAT, CAMPUS_LON, trip.point_lat, trip.point_lon, db)
            # Время с заездом: кампус -> точка пассажира -> точка водителя
            _, duration_via_pass, _ = await get_route(CAMPUS_LAT, CAMPUS_LON, lat, lon, db)
            _, duration_pass_to_driver, _ = await get_route(lat, lon, trip.point_lat, trip.point_lon, db)
            total_duration = duration_via_pass + duration_pass_to_driver
            deviation_minutes = total_duration - duration_direct
            
            if deviation_minutes > max_deviation_minutes:
                continue
        
        # Устанавливаем вычисленные поля
        trip.distance_km = round(distance, 1)
        trip.deviation_minutes = round(deviation_minutes, 0)
        enriched_trips.append(trip)
    
    # Ранжирование: меньше расстояние и меньше отклонение — выше релевантность
    enriched_trips.sort(key=lambda t: (t.distance_km * 0.7 + t.deviation_minutes * 0.3))
    return enriched_trips