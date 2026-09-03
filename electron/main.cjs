const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

app.setName("LOCUS");

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 720,
    title: "LOCUS",
    icon: path.join(__dirname, process.platform === "win32" ? "icon.ico" : "icon.png"),
    backgroundColor: "#09090b",
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  
  const isDev = !app.isPackaged

  if (isDev) {
    win.loadURL("http://localhost:5173");
  } else {
    win.loadFile(path.join(__dirname, "../frontend/dist/index.html"));
  }

  // Allow F12 or Ctrl+Shift+I for DevTools in development
  win.webContents.on("before-input-event", (event, input) => {
    if (input.key === "F12" || (input.control && input.shift && input.key.toLowerCase() === "i")) {
      win.webContents.toggleDevTools();
      event.preventDefault();
    }
  });
}

app.whenReady().then(async () => {
  let backend;

  if (app.isPackaged) {
    // 1. Packaged Production App: Run bundled standalone executable
    const isWin = process.platform === "win32";
    const binaryName = isWin ? "locus-backend.exe" : "locus-backend";
    const backendPath = path.join(process.resourcesPath, "backend", binaryName);

    console.log("[Electron] Spawning bundled backend:", backendPath);
    backend = spawn(backendPath, [], {
      stdio: "inherit",
    });
  } else {
    // 2. Development Mode: Run live FastAPI server with hot-reloading
    console.log("[Electron] Spawning development backend via uv...");
    backend = spawn(
      "uv",
      ["run", "uvicorn", "app.main:app", "--port", "8000", "--reload"],
      {
        cwd: path.join(__dirname, "../backend"),
        stdio: "inherit",
      }
    );
  }

  backend.on("error", (error) => {
    console.error("[Electron] Failed to start backend process:", error);
  });

  app.on("before-quit", () => {
    if (backend) {
      backend.kill();
    }
  });

  function waitForBackend() {
    return new Promise((resolve) => {
      const check = () => {
        const req = http.get("http://localhost:8000/health", () => {
          resolve();
        });

        req.on("error", () => {
          setTimeout(check, 200);
        });
      };

      check();
    });
  }

  await waitForBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
