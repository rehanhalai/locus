"""Generates a realistic 4-channel synchronized H.264 CCTV forensic raw disk image (.dd)."""

import os
import struct
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.modules.carver.ffmpeg import get_ffmpeg_path


def generate_channel_video(cam_id: int, channel_name: str, duration_sec: int = 10) -> str:
    """Generates an H.264 video file with embedded CCTV timestamp HUD using FFmpeg testsrc."""
    tmp = tempfile.NamedTemporaryFile(suffix=".h264", delete=False)
    out_path = tmp.name
    tmp.close()

    patterns = {
        1: "testsrc=size=640x360:rate=25:decimals=1",
        2: "testsrc2=size=640x360:rate=25",
        3: "testsrc=size=640x360:rate=25:decimals=2",
        4: "testsrc=size=640x360:rate=25:decimals=3",
    }
    src = patterns.get(cam_id, "testsrc=size=640x360:rate=25")

    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"{src}:duration={duration_sec}",
        "-c:v",
        "libx264",
        "-profile:v",
        "baseline",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-g",
        "25",
        "-f",
        "h264",
        out_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out_path


def build_dhav_header(
    cam_id: int, is_keyframe: bool, payload_len: int, timestamp: datetime
) -> bytes:
    """Encodes a standard Dahua DHAV 32-byte frame header."""
    header = bytearray(32)
    header[0:4] = b"DHAV"
    header[4] = cam_id - 1  # 0-indexed channel (Camera 1 -> 0, Camera 2 -> 1, ...)
    header[5] = 0xFD if is_keyframe else 0xFC  # Frame type
    header[6] = 0x00
    header[7] = 0x01  # H.264

    struct.pack_into("<I", header, 8, payload_len)

    # Pack DHAV datetime bitfield
    sec = timestamp.second
    minute = timestamp.minute
    hour = timestamp.hour
    day = timestamp.day
    month = timestamp.month
    year = timestamp.year - 2000

    time_bits = (
        (sec & 0x3F)
        | ((minute & 0x3F) << 6)
        | ((hour & 0x1F) << 12)
        | ((day & 0x1F) << 17)
        | ((month & 0x0F) << 22)
        | ((year & 0x3F) << 26)
    )
    struct.pack_into("<I", header, 16, time_bits)
    return bytes(header)


def create_multi_cam_disk_image(output_path: str, duration_sec: int = 15):
    """Interleaves 4 camera H.264 streams into a single raw forensic disk image (.dd)."""
    channels = [
        (1, "Main Entrance"),
        (2, "Cash Counter"),
        (3, "Vault Room"),
        (4, "Perimeter Street"),
    ]

    print(f"[*] Generating {len(channels)} realistic synthetic CCTV camera video streams...")
    cam_files = {}
    for cid, name in channels:
        cam_files[cid] = generate_channel_video(cid, name, duration_sec=duration_sec)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    base_time = datetime.now(UTC).replace(microsecond=0)
    sector_size = 512

    print(f"[*] Multiplexing streams into raw forensic disk image: {output_path}")
    with open(output_path, "wb") as out_f:
        # Write 2048 reserved sectors at start (Disk Partition Table / MBR Header)
        out_f.write(b"\x00" * (2048 * sector_size))

        # Split and write each camera stream with 32-byte DHAV headers aligned to sectors
        for cid, _ in channels:
            raw_video = Path(cam_files[cid]).read_bytes()
            chunk_size = 32768  # 32 KB per sector chunk
            total_len = len(raw_video)
            offset = 0
            chunk_idx = 0

            while offset < total_len:
                chunk_payload = raw_video[offset : offset + chunk_size]
                is_kf = chunk_idx % 4 == 0
                chunk_time = base_time + timedelta(seconds=chunk_idx)

                header = build_dhav_header(cid, is_kf, len(chunk_payload), chunk_time)
                data_block = header + chunk_payload

                # Pad to 512-byte sector boundary
                padding_len = (sector_size - (len(data_block) % sector_size)) % sector_size
                padded_block = data_block + (b"\x00" * padding_len)

                out_f.write(padded_block)
                offset += chunk_size
                chunk_idx += 1

        # Pad end of disk
        out_f.write(b"\x00" * (1024 * sector_size))

    # Clean up temporary h264 files
    for p in cam_files.values():
        if os.path.exists(p):
            os.remove(p)

    final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[✓] Created Forensic CCTV Disk Image: {output_path} ({final_size_mb:.2f} MB)")


if __name__ == "__main__":
    target = os.path.expanduser("~/Downloads/cctv-dd/multi_cam_cctv_h264.dd")
    create_multi_cam_disk_image(target, duration_sec=15)
