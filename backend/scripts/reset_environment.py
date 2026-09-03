#!/usr/bin/env python3
"""Locus Forensic Suite — Environment & Database Reset Utility.

Cleans all database records, removes all case storage files,
clears carved video clips, exports, and resets locus.db to a clean initial state.

Usage:
    python backend/scripts/reset_environment.py
    or:
    ./scripts/reset.sh
"""

import shutil
import sys
from pathlib import Path

# Add backend directory to sys.path so app modules can be imported
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.session import Base, engine  # noqa: E402


def reset_environment() -> None:
    print("=" * 60)
    print("🛰️  LOCUS FORENSIC SUITE — DATABASE & DATA RESET UTILITY")
    print("=" * 60)

    data_dir = BACKEND_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Remove all old/active database files
    db_filename = settings.DATABASE_URL.replace("sqlite:///", "").replace("./data/", "")
    db_candidates = [data_dir / db_filename, data_dir / "locus.db"]

    for db_path in set(db_candidates):
        if db_path.exists():
            db_path.unlink()
            print(f"🗑️  Deleted Database: {db_path.name}")

    # 2. Re-create pristine database schema
    print(f"📦 Initializing fresh database schema -> {settings.DATABASE_URL}...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database schema initialized successfully.")

    # 3. Purge and recreate all data directories
    subdirs = ["cache", "carved_clips", "exports", "temp_streams", "reports", "storage"]
    print("\n🧹 Purging case evidence, carved video streams, and exports...")
    for sub in subdirs:
        sub_path = data_dir / sub
        if sub_path.exists():
            shutil.rmtree(sub_path, ignore_errors=True)
        sub_path.mkdir(parents=True, exist_ok=True)
        print(f"   📁 Cleaned: data/{sub}/")

    print("\n" + "=" * 60)
    print("✨ LOCUS ENVIRONMENT IS 100% CLEAN & READY FOR TESTING!")
    print("=" * 60)


if __name__ == "__main__":
    reset_environment()
