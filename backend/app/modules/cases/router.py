from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import CaseStatus
from app.db.session import get_db
from app.modules.cases.schemas import CaseCreate, CaseDetailResponse, CaseResponse, CaseUpdate
from app.modules.cases.service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    try:
        new_case = CaseService.create_case(db, payload)
        return new_case
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create case: {str(e)}",
        )


@router.get("/", response_model=list[CaseResponse])
def list_cases(
    status: CaseStatus | None = Query(
        None, description="Filter by case status: ACTIVE, ARCHIVED, CLOSED"
    ),
    search: str | None = Query(
        None, description="Search keyword matching case number, name, or investigator"
    ),
    db: Session = Depends(get_db),
):
    return CaseService.list_cases(db, status=status, search=search)


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    try:
        return CaseService.get_case(db, case_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(case_id: str, payload: CaseUpdate, db: Session = Depends(get_db)):
    try:
        return CaseService.update_case(db, case_id, payload)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str, db: Session = Depends(get_db)):
    try:
        CaseService.delete_case(db, case_id)
        return None
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
