from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..websocket_manager import manager
from ..models import DriverLocation
from ..schemas import DriverLocationSchema
from datetime import datetime

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/trip/{trip_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    trip_id: int,
    db: AsyncSession = Depends(get_db)
):
    await manager.connect(websocket, trip_id)
    try:
        while True:
            # Получаем сообщение от клиента (водитель отправляет координаты)
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "location":
                # Водитель отправляет свои координаты
                loc = DriverLocationSchema(**data)
                # Сохраняем в БД
                db_loc = DriverLocation(
                    trip_id=loc.trip_id,
                    driver_id=data.get("driver_id"),  # нужно передавать driver_id
                    lat=loc.lat,
                    lon=loc.lon,
                    timestamp=datetime.now()
                )
                db.add(db_loc)
                await db.commit()
                
                # Рассылаем всем подписчикам этой поездки
                await manager.broadcast_to_trip(trip_id, {
                    "type": "driver_location",
                    "lat": loc.lat,
                    "lon": loc.lon,
                    "timestamp": loc.timestamp.isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, trip_id)