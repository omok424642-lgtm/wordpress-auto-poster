@echo off
:: ============================================================
:: WordPress 자동 포스팅 - Windows 작업 스케줄러 등록
:: 관리자 권한으로 실행하세요
:: ============================================================

echo WordPress 자동 포스팅 스케줄러를 등록합니다...
echo.

set SCRIPT_DIR=%~dp0
set PYTHON=python

:: 기존 작업 삭제 (재등록 시 충돌 방지)
schtasks /delete /tn "WP_Post_0600" /f >nul 2>&1
schtasks /delete /tn "WP_Post_0900" /f >nul 2>&1
schtasks /delete /tn "WP_Post_1300" /f >nul 2>&1
schtasks /delete /tn "WP_Post_1800" /f >nul 2>&1
schtasks /delete /tn "WP_Post_2100" /f >nul 2>&1

:: 06:00 생활경제
schtasks /create /tn "WP_Post_0600" ^
  /tr "\"%SCRIPT_DIR%run_06.bat\"" ^
  /sc DAILY /st 06:00 ^
  /ru "%USERNAME%" ^
  /f
echo [OK] 06:00 생활경제 등록

:: 09:00 생활건강
schtasks /create /tn "WP_Post_0900" ^
  /tr "\"%SCRIPT_DIR%run_09.bat\"" ^
  /sc DAILY /st 09:00 ^
  /ru "%USERNAME%" ^
  /f
echo [OK] 09:00 생활건강 등록

:: 13:00 지원정책
schtasks /create /tn "WP_Post_1300" ^
  /tr "\"%SCRIPT_DIR%run_13.bat\"" ^
  /sc DAILY /st 13:00 ^
  /ru "%USERNAME%" ^
  /f
echo [OK] 13:00 지원정책 등록

:: 18:00 교대 (생활경제/생활건강)
schtasks /create /tn "WP_Post_1800" ^
  /tr "\"%SCRIPT_DIR%run_18.bat\"" ^
  /sc DAILY /st 18:00 ^
  /ru "%USERNAME%" ^
  /f
echo [OK] 18:00 교대 등록

:: 21:00 트렌드 키워드
schtasks /create /tn "WP_Post_2100" ^
  /tr "\"%SCRIPT_DIR%run_21.bat\"" ^
  /sc DAILY /st 21:00 ^
  /ru "%USERNAME%" ^
  /f
echo [OK] 21:00 트렌드 키워드 등록

echo.
echo ============================================================
echo  등록된 작업 확인:
echo ============================================================
schtasks /query /tn "WP_Post_0600" /fo LIST 2>nul | findstr "작업 이름\|Status\|Next Run"
schtasks /query /tn "WP_Post_0900" /fo LIST 2>nul | findstr "작업 이름\|Status\|Next Run"
schtasks /query /tn "WP_Post_1300" /fo LIST 2>nul | findstr "작업 이름\|Status\|Next Run"
schtasks /query /tn "WP_Post_1800" /fo LIST 2>nul | findstr "작업 이름\|Status\|Next Run"
schtasks /query /tn "WP_Post_2100" /fo LIST 2>nul | findstr "작업 이름\|Status\|Next Run"

echo.
echo ✅ 스케줄러 등록 완료!
echo    작업 스케줄러에서 확인: taskschd.msc
echo.
pause
