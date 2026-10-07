from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_current_user
from app.models import User
from app.schemas import UploadOut
from app.services.uploads import save_image


router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post("", response_model=UploadOut, status_code=201)
async def upload_image(file: UploadFile = File(...), _: User = Depends(get_current_user)):
    file_url, file_name, mime_type = await save_image(file)
    return {"file_url": file_url, "file_name": file_name, "mime_type": mime_type}

