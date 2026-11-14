@echo off
setlocal
python "%~dp0tools\launch_hd.py" %*
exit /b %ERRORLEVEL%
