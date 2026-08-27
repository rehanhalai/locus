import asyncio
import hashlib
import os
import time
from collections.abc import AsyncGenerator
from typing import Any


async def stream_file_hashes(
    file_path: str, chunk_size: int = 1024 * 1024
) -> AsyncGenerator[dict[str, Any]]:
    """
    Asynchronous streaming hasher that yields real-time progress, speed,
    and final cryptographic hashes for Server-Sent Events (SSE).
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Evidence file not found at path: {file_path}")

    total_size = os.path.getsize(file_path)
    sha256_hasher = hashlib.sha256()
    md5_hasher = hashlib.md5()
    processed_bytes = 0

    yield {
        "type": "STARTED",
        "stage": "HASHING",
        "file_path": file_path,
        "total_bytes": total_size,
    }

    start_time = time.time()
    last_broadcast_time = start_time
    last_broadcast_bytes = 0

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256_hasher.update(chunk)
            md5_hasher.update(chunk)
            processed_bytes += len(chunk)

            current_time = time.time()
            if (current_time - last_broadcast_time >= 0.2) or (processed_bytes == total_size):
                time_delta = current_time - last_broadcast_time
                bytes_delta = processed_bytes - last_broadcast_bytes
                speed_mb_s = (bytes_delta / time_delta) / (1024 * 1024) if time_delta > 0 else 0.0

                percent = (
                    round((processed_bytes / total_size) * 100, 1) if total_size > 0 else 100.0
                )

                yield {
                    "type": "PROGRESS",
                    "stage": "HASHING",
                    "percent": percent,
                    "speed": f"{speed_mb_s:.1f} MB/s",
                    "processed_bytes": processed_bytes,
                    "total_bytes": total_size,
                }

                last_broadcast_time = current_time
                last_broadcast_bytes = processed_bytes

            await asyncio.sleep(0)

    final_sha256 = sha256_hasher.hexdigest()
    final_md5 = md5_hasher.hexdigest()

    yield {"type": "HASH_MD5", "md5": final_md5}
    yield {"type": "HASH_SHA256", "sha256": final_sha256}
    yield {
        "type": "COMPLETED",
        "stage": "HASHING",
        "sha256": final_sha256,
        "md5": final_md5,
        "file_size_bytes": processed_bytes,
    }
