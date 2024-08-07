from fastapi import APIRouter

from .main_panel.views import router as main_panel_router

router = APIRouter()
router.include_router(main_panel_router)