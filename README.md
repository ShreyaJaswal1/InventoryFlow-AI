# InventoryFlow AI deployment

The frontend and API are deployed separately so the public site can use GitHub Pages while Python and SQLite run on Render.

## Publish the backend on Render

1. Create a GitHub repository named `InventoryFlow-AI` under `ShreyaJaswal1` and push this folder to its `main` branch.
2. Sign in at <https://render.com> and select **New > Blueprint**.
3. Connect `https://github.com/ShreyaJaswal1/InventoryFlow-AI`. Render reads `render.yaml` and creates the Python API plus a persistent disk.
4. Wait for deployment, then copy the Render service URL, for example `https://inventoryflow-ai-api.onrender.com`.
5. Confirm `<RENDER-URL>/api/health` returns `{ "ok": true, ... }`.

The persistent disk is required: without it, SQLite data may be lost when Render replaces the service instance. Persistent disks require a paid Render plan. The demo login is not authentication; configure real authentication before storing sensitive business data or exposing write access publicly.

## Publish the frontend on GitHub Pages

1. Edit `config.js` and replace `https://REPLACE-WITH-YOUR-RENDER-SERVICE.onrender.com/api` with `<RENDER-URL>/api`.
2. Commit and push the change to the repository's `main` branch.
3. In the repository, open **Settings > Pages** and select **GitHub Actions** as the build and deployment source.
4. Wait for the **Deploy InventoryFlow frontend to GitHub Pages** workflow to complete. The workflow summary shows the actual public URL. For this account/repository it is expected to be `https://shreyajaswal1.github.io/InventoryFlow-AI/` once the repository exists, Pages is enabled, and deployment succeeds.

## Shortcut to open the project in GitHub

<https://github.com/ShreyaJaswal1/InventoryFlow-AI>

The repository link is not the live website URL. The repository must be created and the files pushed before either link will show the project.

## Test and local run

```powershell
python -m unittest -v test_inventory_items.py
python "inventory items.py"
```

Local dashboard: <http://127.0.0.1:8001/>. Local API base: `http://127.0.0.1:8001/api`.
