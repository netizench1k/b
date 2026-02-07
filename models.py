from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(Integer, unique=True, index=True)
    tg_username = Column(String(100))
    first_name = Column(String(100))
    avatar_url = Column(String(500), nullable=True)
    rating = Column(Float, default=5.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Trip(Base):
    __tablename__ = "trips"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"))
    trip_type = Column(String(20))  # 'from_campus' или 'to_campus'
    point = Column(String(200))  # Адрес или название точки
    point_lat = Column(Float, nullable=True)  # Широта
    point_lon = Column(Float, nullable=True)  # Долгота
    departure_time = Column(DateTime)
    seats_total = Column(Integer)
    seats_available = Column(Integer)
    price = Column(Integer)
    comment = Column(Text, nullable=True)
    status = Column(String(20), default="active")  # active, in_progress, completed, cancelled
    max_deviation_km = Column(Integer, default=3)  # На сколько км готов отклоняться
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    driver = relationship("User", backref="trips_as_driver")
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    passenger_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), default="pending")  # pending, confirmed, rejected
    passenger_lat = Column(Float, nullable=True)  # Координаты пассажира для уведомлений
    passenger_lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    trip = relationship("Trip", back_populates="bookings")
    passenger = relationship("User", backref="bookings_as_passenger")