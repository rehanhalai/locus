from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.db.session import Base


class CaseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class PartitionType(StrEnum):
    MBR = "MBR"
    GPT = "GPT"
    RAW = "RAW"
    STANDALONE_FILE = "STANDALONE_FILE"
    UNKNOWN = "UNKNOWN"


class FileSystemType(StrEnum):
    DHFS = "DHFS"  # Dahua / CP PLUS
    HKFS = "HKFS"  # Hikvision
    WFS = "WFS"  # Swann / Generic Asian DVRs
    FAT32 = "FAT32"  # Standard SD Card / USB
    EXFAT = "EXFAT"  # Large SD Cards
    NTFS = "NTFS"  # Windows
    EXT4 = "EXT4"  # Linux
    RAW_STREAM = "RAW_STREAM"  # Unindexed H.264/H.265 NAL
    UNKNOWN = "UNKNOWN"


class DVRBrand(StrEnum):
    DAHUA = "Dahua"
    CP_PLUS = "CP PLUS"
    HIKVISION = "Hikvision"
    WFS_GENERIC = "WFS / Generic DVR"
    UNIVIEW = "Uniview"
    HONEYWELL = "Honeywell"
    TP_LINK = "TP-Link"
    STANDARD_STORAGE = "Standard Storage"
    UNKNOWN = "UNKNOWN"


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

    action = Column(String(64), nullable=False)  # e.g., "CASE_INGESTION", "DEVICE_IDENTIFIED"
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
    device_metadata = relationship(
        "DeviceMetadata", back_populates="evidence", uselist=False, cascade="all, delete-orphan"
    )
    partitions = relationship("Partition", back_populates="evidence", cascade="all, delete-orphan")


class DeviceMetadata(Base):
    __tablename__ = "device_metadata"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    evidence_id = Column(
        String(64), ForeignKey("evidence_files.id"), unique=True, index=True, nullable=False
    )
    partition_type = Column(
        SAEnum(PartitionType), default=PartitionType.UNKNOWN, nullable=True
    )  # "MBR", "GPT", "RAW", "STANDALONE_FILE", "UNKNOWN"
    sector_size = Column(Integer, default=512, nullable=False)
    total_sectors = Column(BigInteger, nullable=True)
    dvr_brand_guess = Column(
        SAEnum(DVRBrand), default=DVRBrand.UNKNOWN, nullable=True
    )  # "Dahua", "Hikvision", "WFS / Generic DVR", etc.
    detected_fs = Column(
        SAEnum(FileSystemType), default=FileSystemType.UNKNOWN, nullable=True
    )  # "DHFS", "HKFS", "WFS", "FAT32", "RAW_STREAM", etc.
    confidence_score = Column(Float, default=0.0, nullable=False)
    analyzed_at = Column(DateTime, default=datetime.now(UTC), nullable=False)

    evidence = relationship("EvidenceFiles", back_populates="device_metadata")


class Partition(Base):
    __tablename__ = "partitions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    evidence_id = Column(String(64), ForeignKey("evidence_files.id"), index=True, nullable=False)
    partition_index = Column(Integer, nullable=False)  # 1, 2, 3, 4
    start_sector = Column(BigInteger, nullable=False)
    end_sector = Column(BigInteger, nullable=True)
    total_sectors = Column(BigInteger, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    file_system = Column(
        SAEnum(FileSystemType), default=FileSystemType.UNKNOWN, nullable=True
    )  # "FAT32", "ext4", "DHFS", "HKFS", "WFS", "RAW_STREAM", "UNKNOWN"
    is_proprietary = Column(Boolean, default=False, nullable=False)
    magic_bytes_found = Column(String(64), nullable=True)

    evidence = relationship("EvidenceFiles", back_populates="partitions")
