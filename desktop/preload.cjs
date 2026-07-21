const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('shieldAI', {
  dashboardUrl: 'http://127.0.0.1:8787',
  mcpEndpoint: 'http://127.0.0.1:8765/mcp',
});
