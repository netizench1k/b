import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import GeocodeCache, RouteCache
from .config import settings
import math

async def geocode_address(address: str, db: AsyncSession):
    """Получить координаты по адресу, используя кэш и Яндекс.Карты"""
    # Сначала ищем в кэше
    result = await db.execute(
        select(GeocodeCache).where(GeocodeCache.address == address)
    )
    cached = result.scalar_one_or_none()
    if cached:
        return cached.lat, cached.lon, cached.formatted_address
    
    # Запрос к Яндекс.Геокодеру
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": settings.YANDEX_GEOCODER_API_KEY,
        "geocode": address,
        "format": "json",
        "results": 1
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    
    try:
        pos = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
        lon, lat = map(float, pos.split())
        formatted = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['metaDataProperty']['GeocoderMetaData']['text']
    except (KeyError, IndexError):
        raise ValueError("Адрес не найден")
    
    # Сохраняем в кэш
    cache_entry = GeocodeCache(
        address=address,
        lat=lat,
        lon=lon,
        formatted_address=formatted
    )
    db.add(cache_entry)
    await db.commit()
    return lat, lon, formatted

async def get_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float, db: AsyncSession):
    """Получить расстояние и время маршрута (с кэшем)"""
    # Проверяем кэш
    result = await db.execute(
        select(RouteCache).where(
            RouteCache.from_lat == from_lat,
            RouteCache.from_lon == from_lon,
            RouteCache.to_lat == to_lat,
            RouteCache.to_lon == to_lon
        )
    )
    cached = result.scalar_one_or_none()
    if cached:
        return cached.distance_km, cached.duration_minutes, cached.polyline
    
    # Запрос к Яндекс.Маршрутизатору
    url = "https://api.routing.yandex.net/v2/route"
    params = {
        "apikey": settings.YANDEX_ROUTING_API_KEY,
        "waypoints": f"{from_lon},{from_lat}|{to_lon},{to_lat}",
        "mode": "driving",
        "results": 1
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    
    try:
        route = data['routes'][0]
        distance_km = route['distance'] / 1000
        duration_minutes = route['duration'] / 60
        polyline = route['polyline']  # если есть
    except (KeyError, IndexError):
        # Если API не доступен, считаем по прямой
        distance_km = haversine(from_lat, from_lon, to_lat, to_lon)
        duration_minutes = distance_km * 2  # предположительно 30 км/ч
        polyline = None
    
    # Сохраняем в кэш
    cache_entry = RouteCache(
        from_lat=from_lat, from_lon=from_lon,
        to_lat=to_lat, to_lon=to_lon,
        distance_km=distance_km,
        duration_minutes=duration_minutes,
        polyline=polyline
    )
    db.add(cache_entry)
    await db.commit()
    return distance_km, duration_minutes, polyline

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c