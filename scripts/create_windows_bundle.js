const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const ROOT_DIR = path.resolve(__dirname, "..");
const DIST_DESKTOP = path.join(ROOT_DIR, "dist_desktop");
const WIN_UNPACKED = path.join(DIST_DESKTOP, "win-unpacked");
const BUNDLE_DIR = path.join(DIST_DESKTOP, "locus-windows-demo");
const ZIP_FILE = path.join(DIST_DESKTOP, "locus-windows-demo.zip");

console.log("=================================================");
console.log("   Building LOCUS Windows Standalone Demo Bundle  ");
console.log("=================================================");

// 1. Build frontend and package windows electron app
console.log("\n[1/4] Building frontend and Windows Electron app...");
execSync("pnpm run package:win", { cwd: ROOT_DIR, stdio: "inherit" });

if (!fs.existsSync(WIN_UNPACKED)) {
  console.error(`[ERROR] win-unpacked directory not found at: ${WIN_UNPACKED}`);
  process.exit(1);
}

// 2. Prepare bundle directory structure
console.log("\n[2/4] Assembling bundle directory structure...");
if (fs.existsSync(BUNDLE_DIR)) {
  fs.rmSync(BUNDLE_DIR, { recursive: true, force: true });
}
if (fs.existsSync(ZIP_FILE)) {
  fs.rmSync(ZIP_FILE, { force: true });
}

fs.mkdirSync(BUNDLE_DIR, { recursive: true });

// Copy packaged Windows Electron app to bundle/app
const appDest = path.join(BUNDLE_DIR, "app");
console.log(`Copying Windows app -> ${appDest}`);
fs.cpSync(WIN_UNPACKED, appDest, { recursive: true });

// Copy backend files (excluding large virtualenvs or cache)
const backendSrc = path.join(ROOT_DIR, "backend");
const backendDest = path.join(BUNDLE_DIR, "backend");
console.log(`Copying backend -> ${backendDest}`);
fs.cpSync(backendSrc, backendDest, {
  recursive: true,
  filter: (src) => {
    const rel = path.relative(backendSrc, src);
    if (!rel) return true;
    const parts = rel.split(path.sep);
    // Ignore .venv, __pycache__, .pytest_cache, .ruff_cache, temporary dd files
    if (
      parts.includes(".venv") ||
      parts.includes("__pycache__") ||
      parts.includes(".pytest_cache") ||
      parts.includes(".ruff_cache") ||
      parts.includes("cache")
    ) {
      return false;
    }
    return true;
  },
});

// 3. Create Windows Launcher & Documentation
console.log("\n[3/4] Generating Windows launcher scripts...");

const batContent = `@echo off
title LOCUS Forensic Analysis Platform
color 0B
echo ===============================================================================
echo                 LOCUS Multi-Vendor DVR/NVR Forensic Workstation               
echo ===============================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "APP_DIR=%SCRIPT_DIR%app"

echo [1/2] Launching Forensic API Backend (FastAPI + SQLite)...
cd /d "%BACKEND_DIR%"

where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo   - Detected Astral 'uv', booting server...
    start "LOCUS API Engine" /min uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        echo   - Detected system Python, booting server...
        start "LOCUS API Engine" /min python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    ) else (
        echo.
        echo [ERROR] Neither 'uv' nor 'python' was found in your system PATH!
        echo Please ensure Python 3.12+ (or Astral uv) is installed to run the backend API.
        echo.
        pause
        exit /b 1
    )
)

echo [2/2] Launching LOCUS Desktop Application...
timeout /t 2 /nobreak >nul
cd /d "%APP_DIR%"
start "" "LOCUS.exe"

echo.
echo ===============================================================================
echo  LOCUS is now running! You can safely leave this console minimized.
echo ===============================================================================
`;

fs.writeFileSync(path.join(BUNDLE_DIR, "start_locus.bat"), batContent, "utf8");

const readmeContent = `===============================================================================
                     LOCUS Forensic Workstation (Windows Demo)
===============================================================================

Requirements:
- Windows 10 or 11 (64-bit)
- Python 3.12+ installed (or Astral 'uv' package manager)

How to Run:
1. Double-click "start_locus.bat"
2. The batch script will automatically:
   - Start the local Python forensic backend on http://127.0.0.1:8000
   - Launch the native LOCUS.exe desktop application window

Included in this bundle:
- app/        : Native Windows Electron desktop client with custom brand icons
- backend/    : FastAPI engine with bundled Windows forensic tools (ffmpeg.exe, dc3dd.exe)
- start_locus.bat : 1-click startup launcher
===============================================================================
`;

fs.writeFileSync(path.join(BUNDLE_DIR, "README.txt"), readmeContent, "utf8");

// 4. Create ZIP archive
console.log("\n[4/4] Creating zip archive: locus-windows-demo.zip...");
try {
  execSync(`zip -r "${ZIP_FILE}" "locus-windows-demo"`, {
    cwd: DIST_DESKTOP,
    stdio: "inherit",
  });
  console.log(`\nSUCCESS! Demo package ready at:`);
  console.log(`- Folder: ${BUNDLE_DIR}`);
  console.log(`- Archive: ${ZIP_FILE}`);
} catch (err) {
  console.warn("Zip command failed, folder is available at:", BUNDLE_DIR);
}
