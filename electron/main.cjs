const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http")

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 720,
    title: "LOCUS",
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

  const backendPath = app.isPackaged
    ? path.join(process.resourcesPath, "backend", "locus-backend")
    : path.join(__dirname, "../backend/dist/locus-backend");

  console.log("Backend path:", backendPath);

  const backend = spawn(
    backendPath,
    [],
    {
      stdio: "inherit",
    }
  );

  backend.on("error", (error) => {
    console.error("Failed to start backend:", error);
  });

  app.on("before-quit", () => {
    backend.kill();
  });

  function waitForBackend() {
    return new Promise((resolve) => {
      const check = () => {
        const req = http.get("http://localhost:8000", () => {
          resolve();
        });

      req.on("error", () => {
        setTimeout(check, 200);
      });
    };

    check();
  });
}
  await waitForBackend()
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
