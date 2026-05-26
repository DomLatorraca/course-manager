from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.dependencies import require_admin
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import change_password, create_user


router = APIRouter(prefix="/api/users", tags=["api-users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def api_list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=UserRead)
def api_create_user(data: UserCreate, db: Session = Depends(get_db)):
    try:
        return create_user(db, data.username, data.password, data.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{user_id}/password", response_model=UserRead)
def api_change_password(user_id: int, password: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="La password deve avere almeno 8 caratteri.")
    return change_password(db, user, password)

