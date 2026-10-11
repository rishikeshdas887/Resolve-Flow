"""Shared envelope types."""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


def make_page(items: list[T], total: int, page: int, size: int) -> Page[T]:
    pages = max(1, (total + size - 1) // size)
    return Page(items=items, total=total, page=page, size=size, pages=pages)
