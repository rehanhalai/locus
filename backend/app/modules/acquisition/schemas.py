from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class CloneRequest(BaseModel):
    case_id: str = Field(..., description="Target Case ID, e.g. case_bf70e664")
    source_device: str = Field(..., description="Physical block device (e.g. /dev/sdb) or raw file path")
    image_filename: Optional[str] = Field(None, description="Optional target image name (e.g. evidence_01.dd)")
    investigator: Optional[str] = Field("Forensic Officer", description="Name/badge of investigator performing acquisition")

class CloneResponse(BaseModel):
    task_id: str
    status: str
    case_id: str
    source_device: str
    output_path: str

class TaskResponse(BaseModel):
    task_id: str
    case_id: str
    source_device: str
    output_path: str
    status: str
    latest_event: Optional[Dict[str, Any]] = None
    created_at: str
