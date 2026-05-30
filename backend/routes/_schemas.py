"""Shared Pydantic models used across multiple route modules."""
from typing import Dict, Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class SnifferPayload(BaseModel):
    service: str
    type: str
    url: str
    headers: Optional[Dict[str, str]] = None
    title: str = ""
