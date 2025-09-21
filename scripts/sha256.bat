@echo off
setlocal enabledelayedexpansion
if "%~1"=="" (
  echo Uso: %~nx0 caminho\para\arquivo.exe
  exit /b 1
)
certutil -hashfile "%~1" SHA256
