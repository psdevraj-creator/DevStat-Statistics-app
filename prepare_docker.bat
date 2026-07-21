@echo off
REM Prepare Docker build context by copying frontend source
REM Run this before: gcloud builds submit --source=.
cd /d "%~dp0"
echo Copying frontend source into build context...
if exist "frontend" rmdir /s /q "frontend"
xcopy /E /I /Y "..\..\frontend" "frontend\"
echo Done. Ready for: gcloud builds submit --source=.