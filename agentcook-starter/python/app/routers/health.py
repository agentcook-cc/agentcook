from fastapi import APIRouter

from app.config import VERSION, settings
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=VERSION,
        mock_mode=settings.mock_mode,
        model="mock" if settings.mock_mode else settings.model_name or "auto",
    )
