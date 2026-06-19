#!/bin/bash
set -e
echo "=== DevStat Cloud Run Startup ==="
echo "Testing Python imports..."
cd /app/backend
python3 -c "
import sys
sys.path.insert(0, '/app/backend')
modules = [
    'fastapi', 'uvicorn', 'pydantic', 'pandas', 'numpy',
    'scipy', 'statsmodels', 'sklearn', 'lifelines',
    'plotly', 'matplotlib', 'seaborn', 'jinja2',
    'openpyxl', 'xlsxwriter', 'pyreadstat',
    'factor_analyzer', 'pingouin',
]
for m in modules:
    try:
        __import__(m)
        print(f'  OK  {m}')
    except Exception as e:
        print(f'  FAIL {m}: {e}')
        sys.exit(1)
print('All imports OK')
"
echo "Starting uvicorn..."
exec uvicorn app.main:create_app --host 0.0.0.0 --port ${PORT:-8080} --factory
