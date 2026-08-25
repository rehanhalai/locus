from fastapi import FastAPI
import app.db.models
from app.db.session import Base,engine


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Locus API",
    description="Locus APIMulti-Vendor DVR/NVR Forensic Analysis & Recovery Tool",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return {
        "status": "online"
    }