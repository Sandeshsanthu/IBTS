import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from app.router import router
from app import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bootstrapping DynamoDB table...")
    store.ensure_table_exists()
    logger.info("DynamoDB table ready. Service starting.")
    yield
    logger.info("Service shutting down.")


app = FastAPI(
    title="Idempotency Guard",
    description="Atomic idempotency services for IBTS payment switch",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors())
    return JSONResponse(status_code=422, content={
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": 422,
        "message": errors,
    })


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": 500,
        "message": "Internal server error",
    })


@app.get("/actuator/health")
def health():
    return {"status": "UP"}