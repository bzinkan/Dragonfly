"""Dragonfly API entry point.

FastAPI app wrapped with Mangum for Lambda. Also runnable locally via
`uvicorn app.main:app --reload` for development.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration.

    Loaded once at cold start. Never read os.environ directly elsewhere.
    """

    model_config = SettingsConfigDict(env_prefix="DRAGONFLY_", env_file=".env")

    env: str = "local"  # local | dev | staging | prod
    table_name: str = "Dragonfly"
    s3_bucket: str = "dragonfly-photos-local"
    aws_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    inat_project_id: str = ""
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:19006"]  # Expo web dev server


settings = Settings()


def configure_logging() -> None:
    """Structured JSON logs to stdout. CloudWatch ingests as-is."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = structlog.get_logger()
    log.info("api.startup", env=settings.env, table=settings.table_name)
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="Dragonfly API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    env: str
    version: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness probe. Does not touch DynamoDB.

    Phase 0 exit criterion: this endpoint returns 200 from the deployed
    Lambda, and the Expo app can display its response.
    """
    return HealthResponse(status="ok", env=settings.env, version=app.version)


# Lambda entry point. API Gateway invokes this.
handler = Mangum(app, lifespan="on")
