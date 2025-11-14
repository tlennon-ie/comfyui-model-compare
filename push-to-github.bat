@echo off
REM Quick push script for comfyui-model-compare repository
REM This script helps you push changes to GitHub with proper message formatting

cd /d e:\AI\Comf\ComfyUI\custom_nodes\comfyui-model-compare

REM Check if git is installed
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Git is not installed or not in PATH
    pause
    exit /b 1
)

REM Show current status
echo.
echo ========================================
echo ComfyUI Model Compare - Git Status
echo ========================================
echo.
git status
echo.

REM Ask if user wants to continue
set /p continue="Do you want to push these changes? (y/n): "
if /i not "%continue%"=="y" (
    echo Push cancelled.
    exit /b 0
)

REM Get commit message
echo.
echo Enter commit message (e.g., "fix: Update grid layout algorithm"):
set /p message="Message: "

REM Add all changes
git add .

REM Commit
echo.
echo Committing changes...
git commit -m "%message%"

REM Push to GitHub
echo.
echo Pushing to GitHub...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Changes pushed to GitHub
    echo ========================================
    echo.
    echo View your repository at:
    echo https://github.com/tlennon-ie/comfyui-model-compare
) else (
    echo.
    echo ERROR: Failed to push changes
    echo Please check your GitHub credentials
)

pause
