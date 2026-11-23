@echo off
cd /d "%~dp0"
title Link Export Service (127.0.0.1:8765)
chcp 65001 >nul
echo.
echo  ============================================================
echo   Link Export Service  -  keep this window open
echo   Page: column -> Detail feed -> Batch export
echo  ============================================================
echo.
python _link_export_server.py
if errorlevel 1 (
  echo.
  echo  Service stopped with an error. Is Python on PATH?
)
pause
