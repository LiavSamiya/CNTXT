const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

const projectRoot = path.resolve(__dirname, '..');
const python = process.env.SHIELDAI_PYTHON || 'python';
let processes = [];

function startLocalService(script) {
  const child = spawn(python, [path.join(projectRoot, 'backend', script)], {
    cwd: projectRoot,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.on('error', (error) => {
    dialog.showErrorBox('ShieldAI could not start', `Unable to run ${script} with ${python}.\n\n${error.message}`);
  });
  processes.push(child);
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1050,
    minHeight: 700,
    backgroundColor: '#07131e',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  window.loadURL('http://127.0.0.1:8787');
}

app.whenReady().then(() => {
  startLocalService('app.py');
  startLocalService('mcp_http.py');
  // The local Python app begins immediately; a short wait avoids a white
  // window on the first run while still keeping all traffic on localhost.
  setTimeout(createWindow, 650);
});

app.on('window-all-closed', () => app.quit());
app.on('will-quit', () => processes.forEach((child) => child.kill()));
