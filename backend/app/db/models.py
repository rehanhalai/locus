from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.db.session import Base


class CaseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(64), primary_key=True, index=True)  # e.g., "case_a1b2c3d4"
    case_number = Column(
        String(64), unique=True, index=True, nullable=False
    )  # e.g., "LOCUS-2026-001"
    case_name = Column(String(255), nullable=False)
    investigator = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(CaseStatus), default=CaseStatus.ACTIVE, nullable=False)
    storage_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC), nullable=False
    )

    evidence_files = relationship(
        "EvidenceFiles", back_populates="case", cascade="all, delete-orphan"
    )


class IntegrityStatus(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(String(64), index=True, nullable=True)
    evidence_id = Column(String(64), index=True, nullable=True)

    action = Column(String(64), nullable=False)  # e.g., "CASE_INGESTION", "OFFSET_CALIBRATION"
    actor = Column(String(128), default="Forensic Officer")  # Who performed the action
    details = Column(Text, nullable=True)  # e.g., "Baseline SHA-256 computed: e3b0c44..."
    integrity_status = Column(SAEnum(IntegrityStatus), default=IntegrityStatus.VERIFIED)
    timestamp = Column(DateTime, default=datetime.now(UTC), nullable=False)


class EvidenceFiles(Base):
    __tablename__ = "evidence_files"

    id = Column(String(64), primary_key=True, index=True)  # e.g., "ev_a3f5b8c9"
    case_id = Column(String(64), ForeignKey("cases.id"), index=True, nullable=False)
    source_type = Column(String(32), nullable=False)  # "PHYSICAL_DEVICE" or "IMAGE_FILE"
    source_device = Column(String(255), nullable=True)  # e.g., "/dev/sdb" or original filename
    file_path = Column(Text, nullable=False)  # Absolute path to the .raw/.dd image
    file_size_bytes = Column(BigInteger, nullable=False)

    # Dual Cryptographic Hashes (Baseline)
    sha256_hash = Column(String(64), nullable=False)
    md5_hash = Column(String(32), nullable=False)

    bad_sectors_count = Column(Integer, default=0)
    write_block_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False)

    case = relationship("Case", back_populates="evidence_files")
