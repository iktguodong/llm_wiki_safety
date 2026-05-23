import electron from 'electron';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const { app, BrowserWindow, dialog } = electron;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DEV_SERVER_URL = 'http://127.0.0.1:5173';
const BACKEND_PORT = Number(process.env.ANNIU_BACKEND_PORT || '8000');
const BACKEND_HOST = process.env.ANNIU_BACKEND_HOST || '127.0.0.1';
const BACKEND_BASE_URL = process.env.ANNIU_API_BASE || `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const BACKEND_HEALTH_URL = `${BACKEND_BASE_URL}/api/health`;
const BACKEND_BINARY_NAME = process.platform === 'win32' ? 'anniu-backend.exe' : 'anniu-backend';

let mainWindow = null;
let backendProcess = null;
const gotSingleInstanceLock = app.requestSingleInstanceLock();

if (!gotSingleInstanceLock) {
  app.quit();
}

function getProjectRoot() {
  return path.resolve(app.getAppPath(), '..');
}

function resolveBackendBinaryPath() {
  const packagedPath = path.join(process.resourcesPath, 'backend', BACKEND_BINARY_NAME);
  if (app.isPackaged && fs.existsSync(packagedPath)) {
    return packagedPath;
  }

  const localReleasePath = path.join(getProjectRoot(), 'backend-release', BACKEND_BINARY_NAME);
  if (fs.existsSync(localReleasePath)) {
    return localReleasePath;
  }

  return null;
}

function resolveWindowIconPath() {
  if (app.isPackaged) {
    if (process.platform === 'win32') {
      const packagedIcon = path.join(process.resourcesPath, 'app-icons', 'anniu.ico');
      if (fs.existsSync(packagedIcon)) {
        return packagedIcon;
      }
    } else {
      const packagedIcon = path.join(process.resourcesPath, 'app-icons', 'anniu.png');
      if (fs.existsSync(packagedIcon)) {
        return packagedIcon;
      }
    }
  } else {
    if (process.platform === 'win32') {
      const localIcon = path.join(getProjectRoot(), 'frontend', 'app-icons', 'anniu.ico');
      if (fs.existsSync(localIcon)) {
        return localIcon;
      }
    } else {
      const localIcon = path.join(getProjectRoot(), 'frontend', 'public', 'anniu-logo.png');
      if (fs.existsSync(localIcon)) {
        return localIcon;
      }
    }
  }

  return null;
}

async function isBackendHealthy() {
  try {
    const response = await fetch(BACKEND_HEALTH_URL, { method: 'GET' });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForBackend(timeoutMs = 30_000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await isBackendHealthy()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function spawnBackendProcess() {
  const binaryPath = resolveBackendBinaryPath();
  const appDataRoot = path.join(app.getPath('home'), '.anniu');
  const env = {
    ...process.env,
    ANNIU_BACKEND_HOST: BACKEND_HOST,
    ANNIU_BACKEND_PORT: String(BACKEND_PORT),
    ANNIU_RELOAD: '0',
    ANNIU_API_BASE: BACKEND_BASE_URL,
    ANNIU_APP_DATA_ROOT: appDataRoot,
  };

  if (binaryPath) {
    backendProcess = spawn(binaryPath, [], {
      env,
      stdio: 'inherit',
      windowsHide: true,
    });
    return;
  }

  if (app.isPackaged) {
    throw new Error('未找到桌面版后端二进制文件，请先在 CI 中构建 backend-release。');
  }

  const pythonExecutable = process.env.PYTHON || 'python3';
  backendProcess = spawn(
    pythonExecutable,
    ['-m', 'uvicorn', 'backend.app:app', '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)],
    {
      cwd: getProjectRoot(),
      env,
      stdio: 'inherit',
      windowsHide: true,
    },
  );
}

async function ensureBackendReady() {
  if (await isBackendHealthy()) {
    process.env.ANNIU_API_BASE = BACKEND_BASE_URL;
    return;
  }

  spawnBackendProcess();
  process.env.ANNIU_API_BASE = BACKEND_BASE_URL;

  const ready = await waitForBackend();
  if (!ready) {
    throw new Error(`后端启动超时：${BACKEND_HEALTH_URL}`);
  }
}

function createMainWindow() {
  const iconPath = resolveWindowIconPath();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1280,
    minHeight: 820,
    backgroundColor: '#F8FAFC',
    title: '安牛',
    icon: iconPath || undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

async function loadAppWindow() {
  const win = createMainWindow();

  if (!app.isPackaged) {
    await win.loadURL(DEV_SERVER_URL);
    win.webContents.openDevTools({ mode: 'detach' });
    return;
  }

  const indexHtml = path.join(app.getAppPath(), 'dist', 'index.html');
  await win.loadFile(indexHtml);
}

async function bootApp() {
  if (!gotSingleInstanceLock) {
    app.quit();
    return;
  }

  const iconPath = resolveWindowIconPath();
  if (iconPath && process.platform === 'darwin' && app.dock?.setIcon) {
    app.dock.setIcon(iconPath);
  }

  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.focus();
    }
  });

  await ensureBackendReady();
  await loadAppWindow();
}

app.on('before-quit', () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.whenReady().then(bootApp).catch(async (error) => {
  console.error('Failed to boot app:', error);
  dialog.showErrorBox('安牛启动失败', error instanceof Error ? error.message : String(error));
  app.quit();
});
