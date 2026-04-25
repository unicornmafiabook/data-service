from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.investors import router as investors_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.enrichment import router as enrichment_router

app = FastAPI(
    title="VC Data Service",
    description="Ingests VC datasets into Supabase Postgres and exposes investor search endpoints.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(investors_router)
app.include_router(ingest_router)
app.include_router(enrichment_router)


@app.get("/")
def root():
    return {"service": "vc-data-service", "status": "running", "docs": "/docs"}
