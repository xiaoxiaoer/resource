"""
资源置换评估系统 — Web 应用入口

启动: python -m web.app
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.config import BASE_DIR
from web.routers import pages, api, ws

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)

app = FastAPI(title="资源置换评估系统")

# 静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

# 路由
app.include_router(pages.router)
app.include_router(api.router)
app.include_router(ws.router)


if __name__ == "__main__":
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
