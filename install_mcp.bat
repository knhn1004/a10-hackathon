@echo off
REM Universal MCP Server Installation Script for Windows

setlocal enabledelayedexpansion

REM Detect the project directory (where this script is located)
set "PROJECT_DIR=%~dp0"
REM Remove trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

REM Convert backslashes to forward slashes for JSON
set "PROJECT_DIR_JSON=%PROJECT_DIR:\=/%"

set "CLAUDE_CONFIG=%APPDATA%\Claude\claude_desktop_config.json"

echo ================================================================================
echo   Code Sandbox MCP Server - Installation (Windows)
echo ================================================================================
echo.
echo [*] Detected OS: Windows
echo [*] Project directory: %PROJECT_DIR%
echo.

REM Check prerequisites
echo Checking prerequisites...
echo.

REM Check Poetry
where poetry >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] Poetry not found
    echo Install it with: pip install poetry
    echo Or visit: https://python-poetry.org/docs/#installation
    exit /b 1
)

REM Get absolute path to poetry
for /f "tokens=*" %%i in ('where poetry') do set "POETRY_PATH=%%i"
REM Convert backslashes to forward slashes for JSON
set "POETRY_PATH_JSON=%POETRY_PATH:\=/%"
echo [OK] Poetry installed at: %POETRY_PATH%

REM Check Docker
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] Docker not found
    echo Install Docker Desktop from: https://www.docker.com/products/docker-desktop
    exit /b 1
)
echo [OK] Docker installed

REM Check if Docker is running
docker info >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Docker daemon not running
    echo Please start Docker Desktop and try again
    exit /b 1
)
echo [OK] Docker is running
echo.

REM Install Python dependencies
echo Installing Python dependencies...
cd /d "%PROJECT_DIR%"
poetry install --no-root
echo [OK] Dependencies installed
echo.

REM Check if Docker image exists, build if not
echo Checking Docker image...
docker images | findstr "code-sandbox" >nul
if %ERRORLEVEL% neq 0 (
    echo Building Docker image (this may take a few minutes)...
    docker build -t code-sandbox:latest "%PROJECT_DIR%"
    echo [OK] Docker image built
) else (
    echo [OK] Docker image exists
)
echo.

REM Generate Claude Desktop config
echo Generating Claude Desktop configuration...

REM Create config directory if it doesn't exist
if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"

REM Create backup if config exists
if exist "%CLAUDE_CONFIG%" (
    set "BACKUP=%CLAUDE_CONFIG%.backup.%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
    echo Creating backup...
    copy "%CLAUDE_CONFIG%" "!BACKUP!" >nul
    echo [OK] Backup saved to:
    echo   !BACKUP!
    echo.
)

REM Generate the config with absolute poetry path and relative script path
(
echo {
echo   "mcpServers": {
echo     "code-sandbox": {
echo       "command": "%POETRY_PATH_JSON%",
echo       "args": [
echo         "-C",
echo         "%PROJECT_DIR_JSON%",
echo         "run",
echo         "python",
echo         "mcp_server.py"
echo       ],
echo       "cwd": "%PROJECT_DIR_JSON%",
echo       "env": {
echo         "SANDBOX_IMAGE": "code-sandbox:latest",
echo         "SANDBOX_TIMEOUT": "300",
echo         "MAX_SANDBOXES": "10"
echo       }
echo     }
echo   }
echo }
) > "%CLAUDE_CONFIG%"

echo [OK] Configuration written to:
echo   %CLAUDE_CONFIG%
echo.
echo   Using:
echo   • Poetry: %POETRY_PATH%
echo   • Project: %PROJECT_DIR%
echo.

echo Please restart Claude Desktop manually
echo.

echo ================================================================================
echo   Installation Complete!
echo ================================================================================
echo.
echo Next steps:
echo   1. Restart Claude Desktop
echo   2. Look for the plug icon in the bottom right corner
echo   3. Click it to verify 'code-sandbox' is connected
echo   4. Test with: 'Create a sandbox'
echo.
echo Expected response:
echo   [OK] Sandbox created successfully!
echo   Sandbox ID: abc12345
echo   Status: ready
echo.
echo Configuration file:
echo   %CLAUDE_CONFIG%
echo.
echo Project directory:
echo   %PROJECT_DIR%
echo.

pause

