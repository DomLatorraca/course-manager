from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.dependencies import get_current_user
from app.services.auth_service import authenticate_user


router = APIRouter(tags=["auth"])
api_router = APIRouter(prefix="/api/auth", tags=["api-auth"])


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)) -> RedirectResponse:
    user = authenticate_user(db, username, password)
    if not user:
        return RedirectResponse("/login?error=Credenziali+non+valide", status_code=status.HTTP_303_SEE_OTHER)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/login")
def api_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)) -> dict[str, object]:
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide.")
    request.session["user_id"] = user.id
    return {"id": user.id, "username": user.username, "role": user.role.value}


@api_router.post("/logout")
def api_logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"message": "Logout effettuato."}


@api_router.get("/me")
def api_me(user=Depends(get_current_user)) -> dict[str, object]:
    return {"id": user.id, "username": user.username, "role": user.role.value}

