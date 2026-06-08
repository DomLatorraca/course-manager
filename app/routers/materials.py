from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.material import Material
from app.routers.dependencies import get_current_user, require_admin
from app.schemas.material import MaterialRead
from app.services import course_service
from app.services.file_service import delete_material, get_material_path, guess_material_media_type, save_material


router = APIRouter(prefix="/api/materials", tags=["api-materials"], dependencies=[Depends(get_current_user)])


@router.get("/course/{course_id}", response_model=list[MaterialRead])
def api_list_materials(course_id: int, db: Session = Depends(get_db)):
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    return course.materials


@router.post("/course/{course_id}", response_model=MaterialRead, dependencies=[Depends(require_admin)])
def api_upload_material(
    course_id: int,
    title: str = Form(""),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Corso non trovato.")
    try:
        return save_material(db, course, file, title, description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{material_id}/download")
def api_download_material(material_id: int, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Materiale non trovato.")
    path = get_material_path(material)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File non trovato su storage.")
    return FileResponse(path, filename=material.original_filename)


@router.get("/{material_id}/view")
def api_view_material(material_id: int, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Materiale non trovato.")
    path = get_material_path(material)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File non trovato su storage.")
    media_type = guess_material_media_type(material.original_filename)
    return FileResponse(path, media_type=media_type, headers={"Content-Disposition": f'inline; filename="{material.original_filename}"'})


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def api_delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Materiale non trovato.")
    delete_material(db, material)

