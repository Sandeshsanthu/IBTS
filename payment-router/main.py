from fastapi import FastAPI
from app.routers import route_router

app = FastAPI(title="Payment Router Service")

app.include_router(route_router.router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "UP"}