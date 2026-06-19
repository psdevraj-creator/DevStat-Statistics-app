# DevStat v1.0.0 Release Notes

## Overview

This is the first public release of DevStat, a desktop medical statistics application. This release is packaged as a portable Windows application — no installation or Python required.

## What's Included

- 37+ interactive chart types (histogram, boxplot, violin, ECDF, Q-Q, Pareto, control chart, Sankey, treemap, swimmer, volcano, PCA scatter, correlation heatmap, Bland-Altman, funnel, forest plot, and more)
- Full statistical analysis pipeline (descriptives, group comparisons, regression, survival analysis, diagnostic tests, factor analysis, reliability)
- Chart eligibility engine that checks variable selections and suggests alternatives
- Interactive Plotly charts with zoom, pan, hover, and PNG export
- Publication-quality matplotlib/seaborn export
- Output panel for reviewing and comparing results
- Analysis Wizard for guided test selection
- Sample medical datasets included

## What's Not Included

The following features were removed for the public release:

| Feature | Reason |
|---------|--------|
| **AI Assistant** | Required DeepSeek API key and cloud LLM service |
| **Syntax Editor (R)** | Required R installation; replaced by Python-only engine |

## Build Details

- **Packaging method:** PyInstaller 6.21.0 (onedir mode)
- **Python version:** 3.14.6
- **Frontend:** React 19 + Vite 8 (pre-built, included as static files)
- **Platform:** Windows 10/11 (64-bit)

## Known Limitations

- Maximum file upload size: 50 MB
- Some chart types (hexbin, SPC) require minimum data thresholds (1000+ or 10+ points)
- Very large datasets (>100,000 rows) may cause slow chart rendering
- The R syntax editor is not available (Python-only engine)

## System Requirements

- Windows 10 or later (64-bit)
- 4 GB RAM minimum (8 GB recommended)
- 1 GB free disk space
- No Python, Node.js, or R required

## Changelog

### v1.0.0 (2026-06-13)

- Initial public release
- All 37 chart types implemented and tested
- Eligibility engine integrated across all analysis pages
- Help system with context-sensitive help, glossary, and chart interpretations
- Frontend log store clears on app start
- Backend log clears on server restart
- Cox regression serialization bug fixed
