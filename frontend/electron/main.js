const { app, BrowserWindow, shell, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const licence = require('./licence')

// DevStat offline desktop app — runs the analysis engine 100% locally on
// 127.0.0.1 and loads it in a native window. Data never leaves the machine.
// Licensing (Option A) is handled here via electron/licence.js.
const LOCAL_PORT = Number(process.env.DEVSTAT_LOCAL_PORT || 8210)
const LOCAL_URL = `http://127.0.0.1:${LOCAL_PORT}`
let serverProc = null

function engineCmd() {
  // Packaged: the engine was bundled as extraResources -> resources/engine/
  if (app.isPackaged) {
    const name = process.platform === 'win32' ? 'DevStatEngine.exe' : 'DevStatEngine'
    const exe = path.join(process.resourcesPath, 'engine', name)
    return { cmd: exe, args: [], cwd: path.dirname(exe) }
  }
  // Dev: run backend/run_local.py with the system python.
  const exe = process.env.DEVSTAT_ENGINE_EXE || ''
  if (exe) return { cmd: exe, args: [], cwd: path.dirname(exe) }
  const backend = path.resolve(__dirname, '..', '..', 'backend')
  const py = process.env.DEVSTAT_PYTHON || 'python'
  return { cmd: py, args: [path.join(backend, 'run_local.py')], cwd: backend }
}

function startLocalServer() {
  const e = engineCmd()
  serverProc = spawn(e.cmd, e.args, {
    cwd: e.cwd,
    env: { ...process.env, DEVSTAT_LOCAL_PORT: String(LOCAL_PORT) },
  })
  serverProc.on('error', (err) => console.error('DevStat engine error:', err))
  serverProc.stdout && serverProc.stdout.on('data', (d) => console.log('[engine]', String(d).trim()))
  serverProc.stderr && serverProc.stderr.on('data', (d) => console.error('[engine]', String(d).trim()))
}

function waitForServer(tries = 40) {
  return new Promise((resolve) => {
    let i = 0
    const t = setInterval(async () => {
      try {
        const r = await fetch(`${LOCAL_URL}/api/health`)
        if (r.ok) { clearInterval(t); resolve(true); return }
      } catch {}
      if (++i >= tries) { clearInterval(t); resolve(false) }
    }, 500)
  })
}

let win
async function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 900, minWidth: 980, minHeight: 700,
    title: 'DevStat – Medical Statistics (offline)',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false,
    },
  })
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' } })
  await waitForServer(`${LOCAL_URL}/api/health`)
  win.loadURL(LOCAL_URL)
}

// Renderer asks for the current licence gate state (secure IPC).
ipcMain.handle('licence:state', async () => {
  const c = await licence.checkOnline()
  return licence.gate(c)
})
ipcMain.handle('licence:consume', async () => {
  const c = licence.load() || {}
  c.usageCount = (c.usageCount || 0) + 1
  licence.save(c)
  return licence.gate(c)
})
ipcMain.handle('licence:activate', async () => {
  // Prompt the user to sign in / open checkout in the system browser.
  shell.openExternal(`${licence.BACKEND}/auth`)
  return { opened: true }
})

app.whenReady().then(async () => {
  startLocalServer()
  await createWindow()
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
})

app.on('window-all-closed', () => {
  if (serverProc) { try { serverProc.kill() } catch {} }
  if (process.platform !== 'darwin') app.quit()
})
