from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import api, web
from app.db import get_db
from app.schema import ensure_schema
from app.services import AppError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema(get_db())
    yield


app = FastAPI(title="Invoice Tracker (practice)", lifespan=lifespan)
app.include_router(api.router)
app.include_router(web.router)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=exc.status, content={"errors": exc.messages})
    return web.render_message(request, exc.status, exc.message)


@app.exception_handler(RequestValidationError)
async def bad_json(request: Request, _exc: RequestValidationError):
    message = "The request body does not match the invoice fields."
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=422, content={"errors": [message]})
    return web.render_message(request, 422, message)
