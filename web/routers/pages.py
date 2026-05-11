"""页面路由"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

INDEX_HTML = (Path(__file__).resolve().parent.parent / 'templates' / 'index.html').read_text(encoding='utf-8')


@router.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML
