#!/usr/bin/env python3
"""
Forensic CCTV / DVR Raw Disk Image Generator
Converts 4 synchronized video streams (AVI / MP4) into an authentic
multiplexed raw forensic DVR disk image (.raw / .dd).
"""

import argparse
import os
import struct
import subprocess
import tempfile

# Camera channel tokens matching the Heimvision / Xiongmai OEM specification
CAMERA_TOKENS = {
    1: b"\x3a\xbb\x34\x60",  # Camera 1
    2: b"\x57\x02\x17\x12",  # Camera 2
    3: b"\x69\x5b\x08\x06",  # Camera 3
    4: b"\x6a\x91\x40\x12",  # Camera 4
}


def extract_h264_nal_units(video_path: str, ffmpeg_bin: str) -> list[bytes]:
    """Transcodes a video file to an elementary H.264 stream and splits into NAL units."""
    print(f"[*] Transcoding {os.path.basename(video_path)} to elementary H.264...")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        video_path,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "26",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "25",
        "-f",
        "h264",
        "pipe:1",
    ]
    res = subprocess.run(cmd, capture_output=True, check=True)
    raw_h264 = res.stdout

    # Split into NAL units based on standard start codes \x00\x00\x00\x01
    nal_units = []
    pos = 0
    start_code = b"\x00\x00\x00\x01"
    indices = []
    while True:
        idx = raw_h264.find(start_code, pos)
        if idx == -1:
            break
        indices.append(idx)
        pos = idx + 4

    for i in range(len(indices)):
        start = indices[i]
        end = indices[i + 1] if i + 1 < len(indices) else len(raw_h264)
        nal = raw_h264[start:end]
        if len(nal) > 0:
            nal_units.append(nal)

    print(f"    Extracted {len(nal_units)} NAL units ({len(raw_h264) / (1024 * 1024):.2f} MB)")
    return nal_units


def build_dvr_dat_file(
    cam_files: dict[int, str], out_dat_path: str, ffmpeg_bin: str, start_time: int = 1774345200
):
    """
    Multiplexes NAL units from 4 cameras into an authentic Xiongmai/DVR .DAT container
    with 'luo ' file header and 'liu ' frame packet headers.
    """
    print("[*] Parsing camera feeds...")
    cam_nals = {}
    for cam_id, fpath in cam_files.items():
        if os.path.exists(fpath):
            cam_nals[cam_id] = extract_h264_nal_units(fpath, ffmpeg_bin)
        else:
            print(f"[!] Warning: Camera {cam_id} file not found: {fpath}")

    if not cam_nals:
        raise ValueError("No valid camera video files provided.")

    max_frames = max(len(nals) for nals in cam_nals.values())
    duration_secs = int(max_frames / 25)  # assume ~25 fps
    end_time = start_time + max(1, duration_secs)

    print(
        f"[*] Multiplexing {len(cam_nals)} cameras into CCTV container (duration: {duration_secs}s)..."
    )
    with open(out_dat_path, "wb") as f_out:
        # 1. Write 'luo ' file container header (16 bytes)
        # Magic: 'luo ' (4B), start_timestamp (4B LE), end_timestamp (4B LE), reserved (4B)
        hdr = b"luo " + struct.pack("<II", start_time, end_time) + (b"\x00" * 4)
        f_out.write(hdr)

        # 2. Interleave frames across cameras in temporal lockstep
        for frame_idx in range(max_frames):
            for cam_id, token in CAMERA_TOKENS.items():
                if cam_id not in cam_nals:
                    continue
                nals = cam_nals[cam_id]
                if frame_idx < len(nals):
                    nal = nals[frame_idx]

                    # 32-byte 'liu ' micro-packet header:
                    # 0..4: b"liu "
                    # 4..8: camera token (4 bytes)
                    # 8..12: frame sequence index
                    # 12..32: padding
                    pkt_hdr = b"liu " + token + struct.pack("<I", frame_idx) + (b"\x00" * 20)
                    f_out.write(pkt_hdr)
                    f_out.write(nal)

    total_size = os.path.getsize(out_dat_path)
    print(
        f"[+] Multiplexed container created: {out_dat_path} ({total_size / (1024 * 1024):.2f} MB)"
    )
    return total_size


def create_raw_dvr_image(
    cam_files: dict[int, str], output_raw_path: str, ffmpeg_bin: str, start_time: int = 1788422400
):
    """Generates an authentic FAT32 raw disk image (.raw / .dd) containing the multiplexed DVR container."""
    output_raw = os.path.abspath(output_raw_path)
    os.makedirs(os.path.dirname(output_raw), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        dat_path = os.path.join(tmpdir, "FILE0001.DAT")
        dat_size = build_dvr_dat_file(cam_files, dat_path, ffmpeg_bin, start_time=start_time)

        # Calculate disk image size: data size + 40MB FAT32 overhead
        img_size_mb = max(64, int((dat_size / (1024 * 1024)) + 40))
        print(f"[*] Creating {img_size_mb} MB raw disk image: {output_raw}...")

        if os.path.exists(output_raw):
            os.remove(output_raw)

        # 1. Allocate raw file
        subprocess.run(["truncate", "-s", f"{img_size_mb}M", output_raw], check=True)

        # 2. Format as FAT32
        print("[*] Formatting raw image as forensic FAT32 filesystem...")
        subprocess.run(["mkfs.fat", "-F", "32", output_raw], check=True, stdout=subprocess.DEVNULL)

        # 3. Copy DVR container into root directory of disk image via mcopy
        print("[*] Injecting multiplexed CCTV container into raw disk blocks...")
        subprocess.run(["mcopy", "-i", output_raw, dat_path, "::/FILE0001.DAT"], check=True)

        print("[✔] SUCCESS! Forensic DVR raw image generated:")
        print(f"    File: {output_raw}")
        print(f"    Size: {os.path.getsize(output_raw) / (1024 * 1024):.2f} MB")
        print("    Format: Raw Disk Image (.dd / .raw, FAT32)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert video feeds into an authentic forensic raw DVR disk image."
    )
    parser.add_argument("--cam1", required=True, help="Path to Camera 1 video (AVI/MP4)")
    parser.add_argument("--cam2", required=True, help="Path to Camera 2 video (AVI/MP4)")
    parser.add_argument("--cam3", required=True, help="Path to Camera 3 video (AVI/MP4)")
    parser.add_argument("--cam4", required=True, help="Path to Camera 4 video (AVI/MP4)")
    parser.add_argument("--out", required=True, help="Output .raw or .dd path")
    parser.add_argument(
        "--start-time",
        type=int,
        default=1788422400,
        help="Epoch start timestamp (default: 1788422400)",
    )
    parser.add_argument(
        "--ffmpeg", default="backend/bin/linux/ffmpeg", help="Path to ffmpeg binary"
    )

    args = parser.parse_args()

    cams = {
        1: os.path.abspath(args.cam1),
        2: os.path.abspath(args.cam2),
        3: os.path.abspath(args.cam3),
        4: os.path.abspath(args.cam4),
    }

    create_raw_dvr_image(cams, args.out, os.path.abspath(args.ffmpeg), start_time=args.start_time)


if __name__ == "__main__":
    main()
