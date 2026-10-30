"""
Shared pagination — API Contract Freeze standard.

Every list endpoint accepts `?skip=&limit=` (offset pagination; `limit`
capped at 100, default 20) and returns the `Page[T]` envelope below, so
clients write one parsing path for every paginated resource.
"""
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel):
    skip: int = 0
    limit: int = 20


def pagination_params(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Pagination:
    return Pagination(skip=skip, limit=limit)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int
