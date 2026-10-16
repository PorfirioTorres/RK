@echo off
rem Construye Ryuko.exe (la app completa, con su servidor integrado). Tarda varios minutos y necesita internet.
rem Requisitos: Python 3.10+ (con "Add python.exe to PATH") y Node.js LTS.
setlocal
cd /d "%~dp0"
title Construir Ryuko.exe

set PY=python
%PY% --version >nul 2>nul || set PY=py -3
%PY% --version >nul 2>nul || ( echo [ERROR] No encuentro Python. Instalalo desde python.org y marca "Add python.exe to PATH". & goto fallo )
where npm >nul 2>nul || ( echo [ERROR] No encuentro Node.js. Instalalo desde nodejs.org ^(version LTS^). & goto fallo )

echo.
echo [1/4] Instalando las dependencias de Python (la primera vez tarda varios minutos)...
%PY% -m pip install -r requirements.txt pyinstaller || goto fallo

echo.
echo [2/4] Compilando el servidor (servidor.exe)...
rem Si Ryuko o un servidor.exe viejo siguen abiertos, Windows no deja borrar la carpeta dist\servidor
taskkill /F /IM servidor.exe >nul 2>nul
taskkill /F /IM Ryuko.exe >nul 2>nul
timeout /t 2 /nobreak >nul
if exist dist\servidor rmdir /s /q dist\servidor
if exist dist\servidor (
    echo [ERROR] No puedo borrar dist\servidor: algo lo esta usando. Cierra Ryuko y los servidor.exe del Administrador de tareas,
    echo         y si sigue igual, pausa el antivirus un momento o reinicia la PC. Luego ejecuta este archivo otra vez.
    goto fallo
)
%PY% -m PyInstaller servidor.spec --noconfirm --distpath dist --workpath build\pyinstaller || goto fallo

echo.
echo [3/4] Instalando Electron y el empaquetador...
call npm install || goto fallo

echo.
echo [4/4] Creando la aplicacion (Ryuko.exe)...
node empaquetar.js win32 || goto fallo

echo.
echo ============================================================
echo  Listo:  release\Ryuko-win32-x64\Ryuko.exe
echo  Copia esa carpeta completa donde quieras y abre Ryuko.exe.
echo  Ollama tiene que estar abierto cuando uses la app.
echo ============================================================
echo.
pause
exit /b 0

:fallo
echo.
echo [ERROR] Algo fallo. Revisa los mensajes de arriba (el primer error suele ser la causa).
echo         Si necesitas ayuda, copia el ultimo bloque de mensajes.
echo.
pause
exit /b 1
