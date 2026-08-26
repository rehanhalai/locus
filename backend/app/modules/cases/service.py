import uuid
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.db.models import Case, AuditLog, CaseStatus, IntegrityStatus
from app.modules.cases.schemas import CaseCreate, CaseUpdate

class CaseService:
    @staticmethod
    def _initialize_case_storage(case_id: str) -> str:
        base_dir = Path(settings.DATABASE_URL.replace("sqlite:///", "")).parent.resolve()
        case_dir = base_dir / "storage" / "cases" / case_id
        
        subdirs = ["acquisition", "carved", "thumbnails", "reports"]
        for sub in subdirs:
            (case_dir / sub).mkdir(parents=True, exist_ok=True)
            
        return str(case_dir)

    @classmethod
    def create_case(cls, db: Session, payload: CaseCreate) -> Case:
        existing = db.query(Case).filter(Case.case_number == payload.case_number).first()
        if existing:
            raise ValueError(f"Case with number '{payload.case_number}' already exists.")

        case_id = f"case_{uuid.uuid4().hex[:8]}"
        storage_path = cls._initialize_case_storage(case_id)

        new_case = Case(
            id=case_id,
            case_number=payload.case_number.strip(),
            case_name=payload.case_name.strip(),
            investigator=payload.investigator.strip(),
            description=payload.description.strip() if payload.description else None,
            status=CaseStatus.ACTIVE,
            storage_path=storage_path,
        )
        db.add(new_case)

        audit = AuditLog(
            case_id=case_id,
            action="CASE_CREATED",
            actor=payload.investigator,
            details=f"Case '{payload.case_name}' ({payload.case_number}) created.",
            integrity_status=IntegrityStatus.VERIFIED,
        )
        db.add(audit)
        db.commit()
        db.refresh(new_case)
        return new_case

    @staticmethod
    def list_cases(
        db: Session, 
        status: Optional[CaseStatus] = None, 
        search: Optional[str] = None
    ) -> List[dict]:
        query = db.query(Case)

        if status:
            query = query.filter(Case.status == status)

        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Case.case_number.ilike(term),
                    Case.case_name.ilike(term),
                    Case.investigator.ilike(term)
                )
            )

        cases = query.order_by(Case.created_at.desc()).all()
        
        result = []
        for c in cases:
            c_dict = {
                "id": c.id,
                "case_number": c.case_number,
                "case_name": c.case_name,
                "investigator": c.investigator,
                "description": c.description,
                "status": c.status,
                "storage_path": c.storage_path,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "evidence_count": len(c.evidence_files) if c.evidence_files else 0
            }
            result.append(c_dict)
            
        return result

    @staticmethod
    def get_case(db: Session, case_id: str) -> Case:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case with ID '{case_id}' not found.")
        return case

    @staticmethod
    def update_case(db: Session, case_id: str, payload: CaseUpdate) -> Case:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case with ID '{case_id}' not found.")

        updated_fields = []
        if payload.case_name is not None:
            case.case_name = payload.case_name.strip()
            updated_fields.append("case_name")
        if payload.investigator is not None:
            case.investigator = payload.investigator.strip()
            updated_fields.append("investigator")
        if payload.description is not None:
            case.description = payload.description.strip()
            updated_fields.append("description")
        if payload.status is not None:
            case.status = payload.status
            updated_fields.append(f"status={case.status.value if hasattr(case.status, 'value') else case.status}")

        audit = AuditLog(
            case_id=case_id,
            action="CASE_UPDATED",
            actor=case.investigator,
            details=f"Updated fields: {', '.join(updated_fields)}",
            integrity_status="VERIFIED",
        )
        db.add(audit)
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def delete_case(db: Session, case_id: str) -> bool:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case with ID '{case_id}' not found.")

        audit = AuditLog(
            case_id=case_id,
            action="CASE_DELETED",
            actor=case.investigator,
            details=f"Case '{case.case_name}' ({case.case_number}) deleted.",
            integrity_status="VERIFIED",
        )
        db.add(audit)
        db.delete(case)
        db.commit()
        return True