@echo off
cd /d "%~dp0"
echo Starting Fabric Dye Sample Management System on port 8121...
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8121, log_level='info')"
pause
