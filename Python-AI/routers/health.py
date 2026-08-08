from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK, include_in_schema=False)
async def health_check():
    """Simple health check endpoint."""
    return JSONResponse(content={"status": "healthy"})
