from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
import schemas, models
from database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])

async def get_or_create_user(
    db: AsyncSession,
    tg_id: int,
    tg_username: Optional[str] = None,
    first_name: Optional[str] = None
) -> models.User:
    """Получить или создать пользователя по tg_id."""
    result = await db.execute(
        select(models.User).where(models.User.tg_id == tg_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = models.User(
            tg_id=tg_id,
            tg_username=tg_username,
            first_name=first_name,
            rating=5.0
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

@router.post("/", response_model=schemas.UserResponse)
async def create_user(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать или получить пользователя (используется при первом входе)."""
    user = await get_or_create_user(
        db,
        tg_id=user_data.tg_id,
        tg_username=user_data.tg_username,
        first_name=user_data.first_name
    )
    return user

@router.get("/{tg_id}/trips", response_model=dict)
async def get_user_trips(
    tg_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить поездки пользователя (как водитель и как пассажир)."""
    user = await get_or_create_user(db, tg_id)
    
    # Поездки как водитель
    driver_trips_result = await db.execute(
        select(models.Trip)
        .where(models.Trip.driver_id == user.id)
        .order_by(models.Trip.departure_time.desc())
        .options(selectinload(models.Trip.driver))
    )
    driver_trips = driver_trips_result.scalars().all()
    
    # Бронирования как пассажир
    passenger_bookings_result = await db.execute(
        select(models.Booking)
        .where(models.Booking.passenger_id == user.id)
        .options(
            selectinload(models.Booking.trip)
            .selectinload(models.Trip.driver)
        )
        .order_by(models.Booking.created_at.desc())
    )
    passenger_bookings = passenger_bookings_result.scalars().all()
    
    return {
        "as_driver": driver_trips,
        "as_passenger": passenger_bookings
    }