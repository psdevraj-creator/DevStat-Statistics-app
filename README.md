# DevStat — Medical Statistics Software

**A desktop application for statistical analysis and visualisation of medical and clinical data.**

DevStat provides an interactive, point-and-click interface for performing common medical statistical analyses without requiring programming knowledge. It features over 37 chart types, comprehensive statistical tests, survival analysis, diagnostic test evaluation, and a built-in eligibility engine that guides you to the right analysis.

---

## Features

- **Descriptive Statistics** — means, medians, frequencies, crosstabs, normality tests
- **Group Comparisons** — t-tests, ANOVA, Mann-Whitney U, Wilcoxon, Kruskal-Wallis, chi-square
- **Regression** — linear and logistic regression with stepwise variable selection
- **Survival Analysis** — Kaplan-Meier curves, Cox proportional hazards regression
- **Diagnostic Tests** — sensitivity/specificity, ROC curves with AUC
- **Factor Analysis & Reliability** — exploratory factor analysis, Cronbach's alpha
- **37+ Chart Types** — histogram, boxplot, scatter, violin, ECDF, Q-Q, Pareto, control chart, Sankey, treemap, swimmer plot, volcano plot, PCA scatter, correlation heatmap, Bland-Altman, and more
- **Chart Eligibility Engine** — warns you when variable selections don't match chart requirements and suggests alternatives
- **Interactive Charts** — zoom, pan, hover, download as PNG
- **Publication-Quality Exports** — matplotlib/seaborn static export for journal figures
- **Output Panel** — review, compare, and export all analysis results
- **Wizard** — describe your research question in plain English and get guided to the right test

---

## Download

**End users:** Download the latest portable release from the [Releases](https://github.com/psdevraj-creator/DevStat-Statistics-app/releases) page.

1. Download `DevStat-v1.0.0.zip`
2. Unzip to any folder
3. Double-click `DevStat.exe`
4. Click **Start** to launch the server
5. Open your browser to `http://localhost:8150`

No Python installation required. The app runs entirely offline (no internet connection needed).

---

## Quick Start

1. **Launch** — double-click `DevStat.exe`, click **Start**, then click **Open App**
2. **Upload data** — click the Upload button and select a CSV or Excel file
3. **Explore** — browse your data in the Data View tab, check variable types
4. **Analyse** — choose an analysis from the menu (e.g., Compare Groups, Correlation)
5. **Visualise** — open the Graphs page to create interactive charts
6. **Review** — all results appear in the Output panel

---

## Screenshots

<img width="650" height="462" alt="GUI" src="https://github.com/user-attachments/assets/35dfc490-87ec-4624-a993-36798587cc9f" />
<img width="1877" height="952" alt="Chart" src="https://github.com/user-attachments/assets/a712ddcd-4564-4fa3-9d11-524fa4747d34" />
<img width="1857" height="702" alt="COX" src="https://github.com/user-attachments/assets/30204f8d-b271-44c4-8877-480e1d0aaffc" />
<img width="1882" height="942" alt="KM curve" src="https://github.com/user-attachments/assets/d017e314-b4fd-4d1b-b9e7-334c1f2410ac" />
<img width="1912" height="995" alt="Main Screen" src="https://github.com/user-attachments/assets/f25d5c14-94bf-49c0-bdb9-18e5393965c4" />
<img width="651" height="460" alt="GUI Start" src="https://github.com/user-attachments/assets/0ec15169-ac34-4c82-99c1-bda17b2716fb" />



---

## System Requirements

- **Windows 10 or later** (64-bit)
- **4 GB RAM** (8 GB recommended for large datasets)
- **1 GB free disk space**
- No Python required (bundled with the portable release)

---

## Development Setup

To run from source:

```bash
# Python 3.14 required
pip install -r requirements.txt

# Start backend
cd backend
py -3.14 -m uvicorn app.main:create_app --factory

# Open browser to http://localhost:8150
```

To rebuild the frontend:

```bash
cd frontend
npm install
npm run build
```

---

## What's Not Included in This Release

The following features have been removed from the public release:

- **AI Assistant** — the natural-language analysis assistant required a DeepSeek API key and cloud LLM service. It is not included in this offline release.
- **Syntax Editor** — previously used for running R code against the dataset. Not available in the Python-only engine.

---

## Project Structure

```
DevStat/
├── launcher_gui.py          # Desktop launcher (Tkinter GUI)
├── launch_gui.bat           # Windows batch launcher
├── requirements.txt         # Python dependencies
├── .env.example             # Environment config template
├── sample_*.csv             # Sample medical datasets
├── backend/
│   ├── app/                 # FastAPI backend
│   │   ├── main.py          # Application factory
│   │   ├── config.py        # Configuration
│   │   ├── routers/         # API endpoints
│   │   ├── services/        # Business logic
│   │   ├── models/          # Data models
│   │   └── eligibility.py   # Analysis eligibility engine
│   └── static/              # Built frontend
└── release_preparation/     # Release build workspace
```

---

## Limitations

- Maximum upload file size: 50 MB
- The app requires a local server (started automatically by the launcher)
- Internet access is not required, but some matplotlib exports may attempt online font loading
- For large datasets (>100,000 rows), some chart types may be slow

---

## Privacy & Security

- **All data stays on your machine.** DevStat runs a local server on `127.0.0.1:8150`. No data is sent to external servers.
- The portable release contains no API keys, telemetry, or network callbacks.
- Logs are stored locally and cleared on each restart.

---

## License

This project is provided for educational and research purposes.

---

## Contributing

Contributions are welcome. Please open an issue or pull request on GitHub.
