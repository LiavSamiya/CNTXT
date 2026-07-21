# ShieldAI Desktop

This Electron shell starts two local-only processes:

- Dashboard: `http://127.0.0.1:8787`
- Local MCP HTTP endpoint: `http://127.0.0.1:8765/mcp`

## Run on Windows

```powershell
cd desktop
npm install
$env:SHIELDAI_PYTHON = "C:\Path\To\python.exe"
npm start
```

`SHIELDAI_PYTHON` should point to Python 3.10+ if `python` is not already on
your PATH. The Electron shell stays local; no original connector data is sent
to Electron's main process or an external model.

