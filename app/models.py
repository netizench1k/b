from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Boolean, Interval
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(Integer, unique=True, index=True)
    tg_username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    rating = Column(Float, default=5.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"))
    trip_type = Column(String(20))  # 'from_campus' или 'to_campus'
    
    # Адрес и координаты конечной точки
    point = Column(String(200))
    point_geom = Column(Geometry(geometry_type='POINT', srid=4326))  # PostGIS
    point_lat = Column(Float, nullable=True)  # на всякий случай сохраняем отдельно
    point_lon = Column(Float, nullable=True)
    
    departure_time = Column(DateTime)
    seats_total = Column(Integer)
    seats_available = Column(Integer)
    price = Column(Integer)
    comment = Column(Text, nullable=True)
    status = Column(String(20), default="active")  # active, in_progress, completed, cancelled
    
    # Настройки гибкости
    max_deviation_km = Column(Integer, default=3)
    time_flexibility_minutes = Column(Integer, default=30)  # ±30 минут по умолчанию
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    driver = relationship("User", backref="trips_as_driver")
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")
    locations = relationship("DriverLocation", back_populates="trip", order_by="DriverLocation.timestamp.desc()")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    passenger_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), default="pending")  # pending, confirmed, rejected, completed
    passenger_lat = Column(Float, nullable=True)   # координаты пассажира (для подбора)
    passenger_lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    trip = relationship("Trip", back_populates="bookings")
    passenger = relationship("User", backref="bookings_as_passenger")

class DriverLocation(Base):
    """Текущее местоположение водителя (обновляется через WebSocket)"""
    __tablename__ = "driver_locations"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    driver_id = Column(Integer, ForeignKey("users.id"))
    lat = Column(Float)
    lon = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    trip = relationship("Trip", back_populates="locations")
    driver = relationship("User")

class GeocodeCache(Base):
    """Кэш геокодирования"""
    __tablename__ = "geocode_cache"
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, index=True)
    lat = Column(Float)
    lon = Column(Float)
    formatted_address = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RouteCache(Base):
    """Кэш маршрутов (время и расстояние между двумя точками)"""
    __tablename__ = "route_cache"
    id = Column(Integer, primary_key=True)
    from_lat = Column(Float)
    from_lon = Column(Float)
    to_lat = Column(Float)
    to_lon = Column(Float)
    distance_km = Column(Float)
    duration_minutes = Column(Float)
    polyline = Column(Text, nullable=True)  # закодированный маршрут для карты
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index('idx_from_to', 'from_lat', 'from_lon', 'to_lat', 'to_lon'),
    )