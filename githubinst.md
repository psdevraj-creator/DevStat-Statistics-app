# How to Upload DevStat to GitHub — Step-by-Step Guide

This guide walks you through creating a GitHub repository and uploading DevStat.

---

## Prerequisites

- A [GitHub account](https://github.com/signup)
- The DevStat release files (already prepared in `release_preparation/`)

---

## Step 1: Create a GitHub Repository

1. Go to [github.com](https://github.com) and sign in
2. Click the **+** icon (top-right corner) → **New repository**
3. Fill in:
   - **Repository name:** `DevStat-Statistics-app`
   - **Description:** `Medical Statistics Software — Desktop application for statistical analysis and visualisation of clinical data`
   - **Visibility:** Public
   - **DO NOT** check "Add a README" (we will upload ours)
   - **DO NOT** check "Add .gitignore" (we will upload ours)
4. Click **Create repository**

You will see a page with "Quick setup" instructions. Keep this open.

---

## Step 2: Upload Files (Option A — Via Web Browser)

*Choose this if you do not have Git installed.*

1. On your new empty repository page, click **Add file** → **Upload files**
2. Open `C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\source_clean\` in File Explorer
3. Drag and drop the following into the GitHub upload area:

   ```
   ✓ launcher_gui.py
   ✓ launch_gui.bat
   ✓ launch_gui.vbs
   ✓ stop_devstat.bat
   ✓ launch_devstat.bat
   ✓ requirements.txt
   ✓ sample_100.csv
   ✓ sample_medical_data.csv
   ✓ .gitignore
   ✓ .env.example
   ✓ backend/           (the whole folder)
   ```

4. Now open `C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\docs\` and drag these files into the same upload area:

   ```
   ✓ README.md
   ✓ USER_GUIDE_AND_STATISTICS_MANUAL.md
   ✓ RELEASE_NOTES.md
   ✓ CLEANUP_REPORT.md
   ```

5. Scroll down, add a commit message: `Initial release v1.0.0`
6. Click **Commit changes**

**Done.** Your source code is now on GitHub.

---

## Step 2: Upload Files (Option B — Via Git Command Line)

*Choose this if you have Git installed.*

Open PowerShell or Command Prompt and run:

```bash
cd C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\source_clean

# Initialize Git
git init
git branch -M main

# Add all files
git add .

# Commit
git commit -m "Initial release v1.0.0"

# Add your GitHub repository as remote
git remote add origin https://github.com/psdevraj-creator/DevStat-Statistics-app.git

# Push to GitHub
git push -u origin main
```

Then upload the documentation files:

```bash
cd C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\docs
git add README.md USER_GUIDE_AND_STATISTICS_MANUAL.md RELEASE_NOTES.md CLEANUP_REPORT.md
git commit -m "Add documentation"
git push
```

---

## Step 3: Upload the Portable App as a GitHub Release

1. Go to your repository on GitHub
2. Click **Releases** (right sidebar) → **Create a new release**
3. Fill in:
   - **Tag version:** `v1.0.0`
   - **Release title:** `DevStat v1.0.0`
   - **Description:** Paste the contents of `C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\docs\RELEASE_NOTES.md`
4. **Attach binaries:** Zip the portable app folder:

   ```bash
   # In PowerShell:
   Compress-Archive -Path "C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\output\DevStat-v1.0.0" -DestinationPath "C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\release_preparation\output\DevStat-v1.0.0.zip"
   ```

5. Drag the `.zip` file to the "Attach binaries" area
6. Click **Publish release**

---

## Step 4: Verify Your Repository

After uploading, your GitHub repo should look like this:

```
DevStat/
├── README.md
├── USER_GUIDE_AND_STATISTICS_MANUAL.md
├── RELEASE_NOTES.md
├── CLEANUP_REPORT.md
├── .gitignore
├── .env.example
├── requirements.txt
├── launcher_gui.py
├── launch_gui.bat
├── launch_gui.vbs
├── stop_devstat.bat
├── launch_devstat.bat
├── sample_100.csv
├── sample_medical_data.csv
└── backend/
    ├── app/
    ├── r/
    └── static/
```

The **Releases** section should show `v1.0.0` with the portable app zip attached.

---

## Important Checks Before Publishing

### Security

1. ⚠️ **Check that no `.env` files are in the uploaded files.** The `source_clean/` folder excludes them, but verify manually.
2. ⚠️ **The `_archive/` folder contains a real API key.** It is NOT in `source_clean/`, but if you ever committed it in Git history, the key might be exposed. Consider rotating the DeepSeek API key.
3. ✅ The `.env.example` file contains only placeholders — no real keys.

### What Users Download

Users go to **Releases** → download `DevStat-v1.0.0.zip` → unzip → double-click `DevStat.exe`.

The portable app is **~133 MB** (compressed zip ~60-80 MB).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Upload fails mid-way | Files may be too large. Try uploading in smaller batches. |
| Git push fails "Repository not found" | Check the remote URL is correct: `git remote -v` |
| Git push fails "Permission denied" | You need to authenticate. Use a [GitHub Personal Access Token](https://github.com/settings/tokens) instead of a password. |
| "File too large" error | GitHub has a 100 MB file limit per file. The DevStat.exe is 133 MB — it must go through **Releases**, not the repo directly. |

---

## Need Help?

Open an issue on the GitHub repository or refer to [GitHub's documentation](https://docs.github.com/en/get-started/quickstart/hello-world).
