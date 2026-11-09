@echo off
rem Test double for `ollama` (plan step 14, R14.4): never the real Ollama.
rem `ollama serve` stays alive until it is killed; anything else exits at once.
if /i "%~1"=="serve" (
  ping -n 100000 127.0.0.1 >nul
)
exit /b 0
