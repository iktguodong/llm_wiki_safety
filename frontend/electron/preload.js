import electron from 'electron';

const { contextBridge } = electron;

contextBridge.exposeInMainWorld('anniuRuntime', {
  apiBase: process.env.ANNIU_API_BASE || 'http://127.0.0.1:8000',
});
