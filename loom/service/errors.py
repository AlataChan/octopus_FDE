"""Service error envelope helpers."""
from __future__ import annotations

from fastapi import HTTPException


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": detail})


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"error": detail})


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"error": detail})
