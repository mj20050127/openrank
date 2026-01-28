from fastapi import APIRouter
router = APIRouter(prefix="/api", tags=["todo"])

@router.get("/todo")
def todo():
    return {"todo": True}
