from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.db.models
from app.db.session import Base, engine
from app.modules.acquisition.router import router as acquisition_router
from app.modules.cases.router import router as cases_router
from app.modules.header_parser.router import router as headers_router
from app.modules.identification.router import router as identify_router

# Ensure SQLite tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Locus Forensic Engine API",
    description="Multi-Vendor DVR/NVR Forensic Analysis & Recovery Tool",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router, prefix="/api/v1")
app.include_router(acquisition_router, prefix="/api/v1")
app.include_router(identify_router, prefix="/api/v1")
app.include_router(headers_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "online", "service": "locus-forensic-engine"}
