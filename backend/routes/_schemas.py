"""Shared Pydantic models used across multiple route modules."""
from typing import Dict, Optional, Literal
from pydantic import BaseModel, Field, AnyHttpUrl, AfterValidator
from typing_extensions import Annotated


def url_to_str(v: AnyHttpUrl) -> str:
    return str(v)


StrictUrlStr = Annotated[str, AfterValidator(url_to_str)]


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=256)
    password: str = Field(..., max_length=256)
    variant: Optional[str] = Field(default=None, max_length=64)


class SnifferPayload(BaseModel):
    service: Literal["voyo", "hrti", "eon", "rts", "rtsplaneta", "hbo", "hbomax", "skyshowtime", "manual"]
    type: Literal["mpd", "license", "manifest"]
    url: StrictUrlStr
    headers: Optional[Dict[str, str]] = None
    title: str = Field(default="", max_length=512)

