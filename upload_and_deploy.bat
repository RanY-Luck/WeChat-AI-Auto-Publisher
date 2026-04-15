@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "ZIP_PATH=%CD%\release.zip"
set "REMOTE_USER=root"
set "REMOTE_HOST=159.75.206.103"
set "REMOTE_DIR=/usr/local/ranyong/weachat_ai"

echo [1/5] Checking local release package...
if not exist "%ZIP_PATH%" (
    echo ERROR: Missing release.zip
    echo Run build_release.bat first.
    exit /b 1
)

echo [2/5] Ensuring remote directory exists...
ssh %REMOTE_USER%@%REMOTE_HOST% "mkdir -p %REMOTE_DIR%"
if errorlevel 1 exit /b 1

echo [3/5] Uploading release.zip via scp...
scp "%ZIP_PATH%" %REMOTE_USER%@%REMOTE_HOST%:%REMOTE_DIR%/
if errorlevel 1 exit /b 1

echo [4/5] Running remote deployment steps...
ssh %REMOTE_USER%@%REMOTE_HOST% "cd %REMOTE_DIR% && unzip -o release.zip && chmod +x deploy_centos7.sh && ./deploy_centos7.sh"
if errorlevel 1 exit /b 1

echo [5/5] Showing container status...
ssh %REMOTE_USER%@%REMOTE_HOST% "cd %REMOTE_DIR% && (docker compose ps || docker-compose ps) && echo. && (docker compose logs --tail=50 || docker-compose logs --tail=50)"
if errorlevel 1 exit /b 1

exit /b 0
