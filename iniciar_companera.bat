@echo off
rem Inicia la compañera de escritorio. La primera vez instala Electron (necesita Node.js).
cd /d "%~dp0"
if not exist node_modules (
  echo Instalando Electron por primera vez, esto puede tardar un poco...
  call npm install
)
call npm start
