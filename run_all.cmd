@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Usage:
REM run_scenarios.cmd evaluator.py agent.py start_num end_num

if "%~4"=="" (
    echo Usage: run_all.cmd ^<evaluator.py^> ^<agent.py^> ^<start_num^> ^<end_num^>
    exit /b 1
)

set EVALUATOR=%~1
set AGENT=%~2
set START=%~3
set END=%~4

echo ==================================================================================
echo =================---%AGENT%---=================

for /L %%N in (%START%,1,%END%) do (
    echo =========================================
    echo Running Scenario S%%N
    echo =========================================
    python %EVALUATOR% --team %AGENT% --scenario scenarios/S%%N.json
)

echo.
echo All scenarios completed.
endlocal
