from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK)
async def tools_root():
    """Root endpoint for tools router."""
    return JSONResponse(content={"message": "Tools endpoint"})
