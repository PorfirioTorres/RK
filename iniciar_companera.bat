@echo off
rem Inicia la compañera de escritorio. Si no hay una versión instalada o el código cambió, la construye.
cd /d "%~dp0"

rem Verificar si existe la carpeta de release
if not exist "release\Ryuko-win32-x64\Ryuko.exe" (
    echo [INFO] No se encontro la aplicacion compilada. Iniciando construccion...
    call construir_exe.bat
    if errorlevel 1 (
        echo [ERROR] Fallo la construccion de la app.
        pause
        exit /b 1
    )
)

rem Iniciar la app desde la carpeta de release
echo Iniciando Ryuko...
start "" "release\Ryuko-win32-x64\Ryuko.exe"
exit /b 0

