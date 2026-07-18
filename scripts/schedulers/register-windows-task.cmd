@echo off
rem Registers jj-sync in Windows Task Scheduler (every 15 minutes).
schtasks /Create /F /SC MINUTE /MO 15 /TN "jj-agentic-os vault sync" ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File %USERPROFILE%\jj-agentic-os\scripts\jj-sync.ps1"
