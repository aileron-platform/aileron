"""Browser credential access and rotation API models."""

from pydantic import BaseModel, Field, field_validator


class BrowserIceServer(BaseModel):
    urls: list[str]
    username: str = ""
    credential: str = ""

    @field_validator("urls")
    @classmethod
    def validate_turn_urls(cls, urls: list[str]) -> list[str]:
        if not urls or any(
            not isinstance(url, str)
            or not url.strip()
            or not url.startswith(("turn:", "turns:"))
            for url in urls
        ):
            raise ValueError("ICE server URLs must use the turn or turns scheme")
        return urls


class BrowserAccessResponse(BaseModel):
    browser_url: str = Field(alias="browserUrl")
    password: str
    credential_revision: int = Field(alias="credentialRevision")
    ice_servers: list[BrowserIceServer] = Field(alias="iceServers")

    model_config = {"populate_by_name": True}


class BrowserCredentialRotationResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    credential_revision: int = Field(alias="credentialRevision")
    applied_on_next_start: bool = Field(alias="appliedOnNextStart")

    model_config = {"populate_by_name": True}


__all__ = [
    "BrowserAccessResponse",
    "BrowserCredentialRotationResponse",
    "BrowserIceServer",
]
