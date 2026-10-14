"""Request / response models for the HTTP API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000, description="What the user said")
    session_id: str = Field(
        default="default",
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description="Conversation id; reuse it to continue a conversation",
    )
    user_id: str = Field(default="dev-user", max_length=64, description="Who is asking (used by the beta allowlist)")


class HealthResponse(BaseModel):
    status: str
    version: str
    mock_mode: bool
    model: str


class ToolInfo(BaseModel):
    name: str
    description: str
