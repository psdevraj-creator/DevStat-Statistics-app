// Preload — secure bridge (contextIsolation on, nodeIntegration off).
// Exposes a tiny, safe licence API to the renderer; no direct Node access.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('devstatLicence', {
  state: () => ipcRenderer.invoke('licence:state'),
  consume: () => ipcRenderer.invoke('licence:consume'),
  activate: () => ipcRenderer.invoke('licence:activate'),
})
