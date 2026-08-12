"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, inventory, masters, production, sales, scrap, users, quotations
from app.core.config import get_settings
from app.db.session import Base, engine
from app import models

settings = get_settings()
# Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, masters.router, inventory.router, production.router, scrap.router, sales.router, dashboard.router, users.router, quotations.router):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
