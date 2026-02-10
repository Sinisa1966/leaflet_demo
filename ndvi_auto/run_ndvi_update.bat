@echo off
setlocal
cd /d %~dp0
python download_and_publish.py > ndvi_auto.log 2>&1
