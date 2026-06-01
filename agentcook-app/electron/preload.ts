import { contextBridge, ipcRenderer } from 'electron';

/**
 * Secure bridge between renderer (web) and main (Node) process.
 * Only expose a minimal, type-safe API surface.
 */
contextBridge.exposeInMainWorld('electronAPI', {
  /** App metadata */
  platform: process.platform,
  isElectron: true,

  /** Get the user-data directory for local storage */
  getUserDataPath: (): Promise<string> =>
    ipcRenderer.invoke('get-user-data-path'),

  /** App version from package.json */
  getAppVersion: (): Promise<string> =>
    ipcRenderer.invoke('get-app-version'),
});

/** Type declaration for the exposed API */
export interface ElectronAPI {
  platform: NodeJS.Platform;
  isElectron: boolean;
  getUserDataPath: () => Promise<string>;
  getAppVersion: () => Promise<string>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
