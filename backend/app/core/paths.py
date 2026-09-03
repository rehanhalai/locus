"""Persistent directory and path management for LOCUS forensic application data."""

import os
import platform
import sys
from pathlib import Path


def get_data_dir() -> Path:
    """Returns a persistent, absolute directory for LOCUS data (database, carved clips, exports, cache)."""
    # 1. Explicit environment variable override
    env_dir = os.environ.get("LOCUS_DATA_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. If running locally from repo root in dev mode (where ./backend/data or ./data exists outside PyInstaller /tmp)
    if not getattr(sys, "frozen", False):
        local_backend_data = Path.cwd() / "backend" / "data"
        if local_backend_data.exists():
            return local_backend_data.resolve()

        local_data = Path.cwd() / "data"
        if local_data.exists():
            return local_data.resolve()

    # 3. Persistent OS User Data Directory for packaged desktop app
    system = platform.system().lower()
    if system == "windows":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "LOCUS" if appdata else Path.home() / "AppData" / "Roaming" / "LOCUS"
    elif system == "darwin":
        base = Path.home() / "Library" / "Application Support" / "LOCUS"
    else:
        # Linux / Unix standard XDG data directory
        xdg_data = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg_data) / "locus" if xdg_data else Path.home() / ".local" / "share" / "locus"

    data_dir = (base / "data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_carved_clips_dir() -> Path:
    p = get_data_dir() / "carved_clips"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_exports_dir() -> Path:
    p = get_data_dir() / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    p = get_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_reports_dir() -> Path:
    p = get_data_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p
