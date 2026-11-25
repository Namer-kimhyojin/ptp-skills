@echo off
setlocal
chcp 65001 >nul
set "SKILL_DIR=%~dp0"
set "VENV_PY=%SKILL_DIR%.venv\Scripts\python.exe"

echo.
echo === 포항테크노파크 보도자료 스킬 실행 환경 설치 ===
echo.

rem 1) Python 3.10 이상 찾기: py -3 먼저, 그다음 python
set "PYCMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto found_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto found_python

echo [실패] Python 3.10 이상을 찾지 못했습니다.
echo.
echo Python 3.10 이상을 python.org에서 설치하세요.
echo 설치할 때 'Add python.exe to PATH' 항목에 꼭 체크하세요.
echo 설치한 뒤 이 파일을 다시 실행하면 됩니다.
echo.
pause
exit /b 1

:found_python
echo [1/4] Python 확인 완료: %PYCMD%

echo [2/4] 스킬 전용 실행 환경을 만드는 중입니다...
%PYCMD% -m venv "%SKILL_DIR%.venv"
if errorlevel 1 goto fail
if not exist "%VENV_PY%" goto fail

echo [3/4] 필요한 부품(lxml)을 설치하는 중입니다. 인터넷 연결이 필요합니다...
"%VENV_PY%" -m pip install --disable-pip-version-check lxml
if errorlevel 1 goto fail

> "%SKILL_DIR%runtime-python.txt" echo %VENV_PY%
if errorlevel 1 goto fail

echo [4/4] 설치가 잘 되었는지 점검하는 중입니다...
"%VENV_PY%" "%SKILL_DIR%scripts\self_test.py"
if errorlevel 1 goto fail

echo.
echo [성공] 설치가 끝났습니다. 이제 보도자료 스킬을 사용할 수 있습니다.
echo.
pause
exit /b 0

:fail
echo.
echo [실패] 설치 중 문제가 생겼습니다. 위에 나온 오류 문장을 담당자에게 알려 주세요.
echo.
pause
exit /b 1
