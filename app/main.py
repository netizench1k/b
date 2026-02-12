from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import engine, Base
from .routers import trips, ws, users
from .config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создание таблиц (для PostgreSQL с PostGIS лучше использовать Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="DVFU Ride API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router)
app.include_router(ws.router)
app.include_router(users.router)

@app.get("/")
def root():
    return {"message": "DVFU Ride API is running"}