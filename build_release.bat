@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "RELEASE_DIR=%CD%\release"
set "ZIP_PATH=%CD%\release.zip"
set "TAR_PATH=%RELEASE_DIR%\wechat-ai-publisher.tar"

echo [1/7] Checking required files...
if not exist ".env" (
    echo ERROR: Missing .env
    exit /b 1
)
if not exist "docker-compose.yml" (
    echo ERROR: Missing docker-compose.yml
    exit /b 1
)
if not exist "config\config.py" (
    echo ERROR: Missing config\config.py
    exit /b 1
)
if not exist "deploy_centos7.sh" (
    echo ERROR: Missing deploy_centos7.sh
    exit /b 1
)

set "IMAGE_NAME="
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /I "%%~A"=="IMAGE_NAME" set "IMAGE_NAME=%%~B"
)
if not defined IMAGE_NAME set "IMAGE_NAME=wechat-ai-publisher:latest"

echo [2/7] Preparing release directory...
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\config"
mkdir "%RELEASE_DIR%\cover_pool"

echo [3/7] Building Docker image...
docker build -t "%IMAGE_NAME%" .
if errorlevel 1 exit /b 1

echo [4/7] Saving image tar...
docker save -o "%TAR_PATH%" "%IMAGE_NAME%"
if errorlevel 1 exit /b 1

echo [5/7] Copying deployment files...
copy /y "docker-compose.yml" "%RELEASE_DIR%\docker-compose.yml" >nul
if errorlevel 1 exit /b 1
copy /y ".env" "%RELEASE_DIR%\.env" >nul
if errorlevel 1 exit /b 1
copy /y "config\config.py" "%RELEASE_DIR%\config\config.py" >nul
if errorlevel 1 exit /b 1
copy /y "deploy_centos7.sh" "%RELEASE_DIR%\deploy_centos7.sh" >nul
if errorlevel 1 exit /b 1
if exist "cover_pool" xcopy /e /i /y "cover_pool" "%RELEASE_DIR%\cover_pool" >nul
if errorlevel 1 exit /b 1

echo [6/7] Creating release.zip...
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"
tar.exe -a -cf "%ZIP_PATH%" -C "%RELEASE_DIR%" .
if errorlevel 1 exit /b 1

echo [7/7] Done.
echo Release directory: %RELEASE_DIR%
echo Release zip: %ZIP_PATH%
echo.
echo Included:
echo   - wechat-ai-publisher.tar
echo   - docker-compose.yml
echo   - .env
echo   - config\config.py
echo   - deploy_centos7.sh
echo   - cover_pool\*
echo   - IMAGE_NAME=%IMAGE_NAME%
echo.
echo Not included:
echo   - wechat-profile

exit /b 0
