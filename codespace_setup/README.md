# DevStat — GitHub Codespaces

Run DevStat entirely in your browser — no installation required.

---

## Quick Start

1. **Open in Codespaces**

   Visit the repository:
   **[https://github.com/psdevraj-creator/DevStat-Statistics-app](https://github.com/psdevraj-creator/DevStat-Statistics-app)**

   Click the **Code** button → **Open with Codespaces** → **Create codespace on main**

   *(Or click the "Open in GitHub Codespaces" badge at the top of the README.)*

2. **Wait for setup**

   The container builds and dependencies install automatically (~2–3 minutes).
   You'll see a terminal message: **"Setup complete!"**

3. **Start the app**

   In the Codespaces terminal, run:

   ```bash
   bash codespace_setup/start.sh
   ```

4. **Open the app**

   A notification appears: *"DevStat App forwarded to port 8150"* — click **Open in Browser**.

   *(If no notification, click the **Ports** tab (bottom panel) → find port 8150 → click the globe icon.)*

5. **Use DevStat**

   The app loads in your browser. Upload a CSV or Excel file and start analysing.

---

## What You Get

- Full DevStat interface with all statistical analyses
- 37+ interactive chart types
- Data upload, editing, and export
- Session persists as long as the Codespace is running

## Important Notes

- **Free tier:** GitHub gives 120 core-hours/month free (approx. 60 hours of DevStat use).
- **Inactivity:** Codespaces stop after 30 minutes of inactivity. Your data is lost — download any exports before closing.
- **Data privacy:** All data stays within the Codespace container. GitHub does not access your uploaded files.
- **Internet required:** Unlike the desktop version, Codespaces needs an internet connection.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 8150 not forwarded | Run `bash codespace_setup/start.sh` again |
| "Module not found" errors | Run `bash .devcontainer/setup.sh` to reinstall |
| App sluggish | Upgrade your Codespace machine: Settings → Codespaces → Machine type → 4-core |
| Container won't build | Check the logs in the terminal panel |
