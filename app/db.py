from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped asynchronous database session."""

    async with AsyncSession(request.app.state.engine, expire_on_commit=False) as session:
        yield session
