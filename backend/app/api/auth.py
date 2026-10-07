from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import LoginIn, TokenOut, UserOut


router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user or not verify_password(payload.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not user.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    return {
        "access_token": create_access_token(str(user.id), user.role.value),
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

