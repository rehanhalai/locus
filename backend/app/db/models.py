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
    TP_LINK = "TP-Link / Tapo"
    STANDARD_STORAGE = "Standard Storage"
    UNKNOWN = "UNKNOWN"


class VideoCodec(StrEnum):
    H264 = "H264"
    H265 = "H265"
    MPEG4 = "MPEG4"
    MJPEG = "MJPEG"
    UNKNOWN = "UNKNOWN"


class EventLabel(StrEnum):
    # People
    PERSON = "person"

    # Vehicles & Transportation
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"
    BUS = "bus"
    TRUCK = "truck"
    BOAT = "boat"
    AIRPLANE = "airplane"
    TRAIN = "train"

    # Bags, Luggage & Carried Items (Theft / Robbery)
    BACKPACK = "backpack"
    HANDBAG = "handbag"
    SUITCASE = "suitcase"
    UMBRELLA = "umbrella"

    # Weapons & Potential Threats
    KNIFE = "knife"
    SCISSORS = "scissors"

    # Electronics & Valuables
    CELL_PHONE = "cell phone"
    LAPTOP = "laptop"
    TV = "tv"

    # Animals (Distraction / Intrusion filtering)
    DOG = "dog"
    CAT = "cat"
    HORSE = "horse"
    BIRD = "bird"

    # Infrastructure / Scene Markers
    TRAFFIC_LIGHT = "traffic light"
    FIRE_HYDRANT = "fire hydrant"
    STOP_SIGN = "stop sign"

    # Motion & Fallback
    MOTION = "motion"
    OTHER = "other"


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
    exports = relationship("EvidenceExport", back_populates="case", cascade="all, delete-orphan")


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
    master_sector_maps = relationship(
        "MasterSectorMap", back_populates="evidence", cascade="all, delete-orphan"
    )
    carved_clips = relationship(
        "CarvedClip", back_populates="evidence", cascade="all, delete-orphan"
    )
    timeline_calibrations = relationship(
        "TimelineCalibration", back_populates="evidence", cascade="all, delete-orphan"
    )
    timeline_events = relationship(
        "TimelineEvent", back_populates="evidence", cascade="all, delete-orphan"
    )
    exports = relationship(
        "EvidenceExport", back_populates="evidence", cascade="all, delete-orphan"
    )


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


class MasterSectorMap(Base):
    __tablename__ = "master_sector_map"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    evidence_id = Column(String(64), ForeignKey("evidence_files.id"), index=True, nullable=False)
    camera_id = Column(Integer, index=True, nullable=False)  # Camera 1, 2, 3, 4, ...
    start_sector = Column(BigInteger, index=True, nullable=False)
    end_sector = Column(BigInteger, index=True, nullable=False)
    start_time = Column(DateTime, index=True, nullable=False)
    end_time = Column(DateTime, index=True, nullable=False)
    frame_count = Column(Integer, default=0, nullable=False)
    keyframe_count = Column(Integer, default=0, nullable=False)
    stream_format = Column(
        SAEnum(VideoCodec), default=VideoCodec.H264, nullable=False
    )  # "H264", "H265", "MPEG4", "MJPEG", "UNKNOWN"
    size_bytes = Column(BigInteger, nullable=False)

    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False)

    evidence = relationship("EvidenceFiles", back_populates="master_sector_maps")


class CarvedClip(Base):
    __tablename__ = "carved_clips"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "clip_a8f3b2c1"
    evidence_id = Column(String(64), ForeignKey("evidence_files.id"), index=True, nullable=False)
    camera_id = Column(Integer, index=True, nullable=False)  # Camera 1, 2, 3, 4, ...
    start_time = Column(DateTime, index=True, nullable=False)
    end_time = Column(DateTime, index=True, nullable=False)
    start_sector = Column(BigInteger, nullable=False)
    end_sector = Column(BigInteger, nullable=False)
    codec = Column(
        SAEnum(VideoCodec), default=VideoCodec.H264, nullable=False
    )  # "H264", "H265", "MPEG4"
    file_path = Column(Text, nullable=False)  # Absolute path to carved .mp4 file
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False)  # Forensic proof
    md5_hash = Column(String(32), nullable=False)
    frame_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False)

    evidence = relationship("EvidenceFiles", back_populates="carved_clips")
    timeline_events = relationship(
        "TimelineEvent", back_populates="clip", cascade="all, delete-orphan"
    )
    exports = relationship("EvidenceExport", back_populates="clip")


class TimelineCalibration(Base):
    __tablename__ = "timeline_calibrations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    evidence_id = Column(String(64), ForeignKey("evidence_files.id"), index=True, nullable=False)
    camera_id = Column(Integer, index=True, nullable=False)
    offset_seconds = Column(Float, default=0.0, nullable=False)  # e.g., +240.0 or -15.5
    reason = Column(String(255), nullable=True)  # e.g., "Calibrated with atomic reference clock"
    calibrated_by = Column(String(128), default="Forensic Officer", nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC), nullable=False
    )

    evidence = relationship("EvidenceFiles", back_populates="timeline_calibrations")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "evt_a1b2c3d4e5f6"
    evidence_id = Column(String(64), ForeignKey("evidence_files.id"), index=True, nullable=False)
    clip_id = Column(String(64), ForeignKey("carved_clips.id"), index=True, nullable=True)
    camera_id = Column(Integer, index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)  # Calibrated timestamp of detection
    frame_number = Column(Integer, default=0, nullable=False)
    label = Column(SAEnum(EventLabel), default=EventLabel.PERSON, index=True, nullable=False)

    confidence = Column(Float, nullable=False)  # 0.0 to 1.0 (e.g. 0.94)
    bbox_x = Column(Float, default=0.0, nullable=False)  # Normalized 0.0 - 1.0 (top-left x)
    bbox_y = Column(Float, default=0.0, nullable=False)  # Top-left y
    bbox_w = Column(Float, default=0.0, nullable=False)  # Width
    bbox_h = Column(Float, default=0.0, nullable=False)  # Height
    is_motion = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False)

    evidence = relationship("EvidenceFiles", back_populates="timeline_events")
    clip = relationship("CarvedClip", back_populates="timeline_events")


class EvidenceExport(Base):
    __tablename__ = "evidence_exports"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "exp_a1b2c3d4e5f6"
    evidence_id = Column(String(64), ForeignKey("evidence_files.id"), index=True, nullable=False)
    clip_id = Column(String(64), ForeignKey("carved_clips.id"), index=True, nullable=True)
    case_id = Column(String(64), ForeignKey("cases.id"), index=True, nullable=False)
    camera_id = Column(Integer, index=True, nullable=False)

    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    start_sector = Column(BigInteger, default=0, nullable=False)
    end_sector = Column(BigInteger, default=0, nullable=False)

    exported_filename = Column(String(255), nullable=False)
    exported_file_path = Column(String(512), nullable=False)
    exported_file_size_bytes = Column(BigInteger, default=0, nullable=False)

    sha256_hash = Column(String(64), index=True, nullable=False)  # For reverse-hash lookup
    md5_hash = Column(String(32), nullable=False)

    manifest_json = Column(Text, nullable=False)
    manifest_signature = Column(String(64), nullable=False)

    exported_by = Column(String(128), default="Forensic Officer", nullable=False)
    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False)

    evidence = relationship("EvidenceFiles", back_populates="exports")
    clip = relationship("CarvedClip", back_populates="exports")
    case = relationship("Case", back_populates="exports")
