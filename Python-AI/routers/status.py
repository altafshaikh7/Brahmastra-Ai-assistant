from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/", status_code=status.HTTP_200_OK)
async def status_check():
    """Simple status endpoint returning application version and environment."""
    return JSONResponse(content={"status": "ok"})
