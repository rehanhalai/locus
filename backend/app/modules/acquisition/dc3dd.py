import os
import re
import shutil
import asyncio
import platform
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Any

def get_dc3dd_path() -> Path:
    base_dir = Path(__file__).resolve().parents[3]
    current_os = platform.system().lower()

    if current_os == "windows":
        binary_path = base_dir / "bin" / "windows" / "dc3dd.exe"
    else:
        binary_path = base_dir / "bin" / "linux" / "dc3dd"

    if binary_path.exists() and os.access(binary_path, os.X_OK):
        return str(binary_path)

    system_bin = shutil.which("dc3dd")
    if system_bin:
        return system_bin

    raise FileNotFoundError(
        f"dc3dd binary not found for {current_os}. Checked: {binary_path}"
    )

def get_executable_commmamd_dc3dd(drive_name, output_path):
    return [
        get_dc3dd_path(),
        f"if={drive_name}",
        f"of={output_path}",
        "hash=sha256",
        "hash=md5",
        f"log={output_path}.log"
    ]

def paser_dc3dd_line(line : str ) -> Optional[Dict[str,Any]]:
    sha256_match = re.search(r"([a-fA-F0-9]{64})\s*\(\s*sha256\s*\)|sha256[:\s]+([a-fA-F0-9]{64})", line, re.IGNORECASE)
    if sha256_match:
        hash_val = sha256_match.group(1) or sha256_match.group(2)
        return {"type": "HASH_SHA256", "sha256": hash_val}

    md5_match = re.search(r"([a-fA-F0-9]{32})\s*\(\s*md5\s*\)|md5[:\s]+([a-fA-F0-9]{32})", line, re.IGNORECASE)
    if md5_match:
        hash_val = md5_match.group(1) or md5_match.group(2)
        return {"type": "HASH_MD5", "md5": hash_val}

    progress_match = re.search(r"(?:copied\s*\(\s*(\d+(?:\.\d+)?)%\s*\)|\[(\d+(?:\.\d+)?)%)[^,\n]*?,\s*([\d\.]+\s*[KMGT]?B?/s)", line, re.IGNORECASE)
    if progress_match:
        percent = progress_match.group(1) or progress_match.group(2)
        speed = progress_match.group(3)
        return {
            "type": "PROGRESS",
            "percent": float(percent),
            "speed": speed,
            "raw": line,
        }
    return None


async def run_dc3dd(
    source_path: str,
    output_path: str,
    log_path: Optional[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    executable = get_dc3dd_path()
    log_file = log_path or f"{output_path}.log"
    
    cmd = get_executable_commmamd_dc3dd(source_path, output_path)
    yield {
        "type": "STARTED",
        "source": source_path,
        "output": output_path,
        "log_path": output_path+".log",
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        final_sha256 = None
        final_md5 = None
        error_lines = []
        while True:
            line_bytes = await process.stdout.readline()
            if not line_bytes:
                break

            line = line_bytes.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if "error" in line.lower() or "cannot" in line.lower() or "failed" in line.lower():
                error_lines.append(line)
            
            parsed = paser_dc3dd_line(line)
            if parsed:
                if parsed["type"] == "HASH_SHA256":
                    final_sha256 = parsed["sha256"]
                elif parsed["type"] == "HASH_MD5":
                    final_md5 = parsed["md5"]
                yield parsed

        await process.wait()
        if process.returncode == 0:
            yield {
                "type": "COMPLETED",
                "sha256": final_sha256,
                "md5": final_md5,
                "exit_code": 0,
                "log_path": log_file,
            }
        else:
            err_msg = " | ".join(error_lines) if error_lines else f"dc3dd exited with code {process.returncode}"
            yield {
                "type": "FAILED",
                "exit_code": process.returncode,
                "error": err_msg,
            }   
    except Exception as e:
        yield {
            "type": "ERROR",
            "error": str(e),
        }

if __name__ == "__main__":  
    async def test():
        async for event in run_dc3dd("pyproject.toml","test_out.dd"):
            print(event)
    
    asyncio.run(test())


