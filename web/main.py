import logging

from fastapi import FastAPI
from sqladmin import Admin
from starlette.staticfiles import StaticFiles

from src.admin import register_view
from src.db.models import Base
from src.endpoints import router as main_router
from src.middlewares import MIDDLEWARES

app = FastAPI()

logger_handler = logging.FileHandler(filename='app_log1.log')
logger_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger = logging.getLogger("uvicorn.access")
logger.addHandler(logger_handler)

admin = Admin(app=app, engine=Base.engine, templates_dir='templates')
register_view(admin)
app.include_router(main_router)
for middleware, options in MIDDLEWARES:
    app.add_middleware(middleware, **options)


@app.on_event('startup')
async def start_up():
    async with Base.engine.begin() as conn:
       # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

