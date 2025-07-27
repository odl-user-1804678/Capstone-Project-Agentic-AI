@echo off
echo Starting Git operations for weather app deployment...

REM Check if we're in a git repository
if not exist ".git" (
    echo Initializing Git repository...
    git init
    if %errorlevel% neq 0 (
        echo Error: Failed to initialize Git repository
        exit /b 1
    )
)

REM Configure Git user if not set
git config user.name >nul 2>&1
if %errorlevel% neq 0 (
    echo Setting Git user configuration...
    git config user.name "Multi-Agent System"
    git config user.email "multiagent@example.com"
)

REM Check if index.html exists
if not exist "index.html" (
    echo Error: index.html not found!
    exit /b 1
)

echo Staging index.html...
git add index.html
if %errorlevel% neq 0 (
    echo Error: Failed to stage file
    exit /b 1
)

REM Check for changes
git diff --staged --quiet
if %errorlevel% equ 0 (
    echo No changes to commit.
    exit /b 0
)

echo Committing changes...
git commit -m "Auto-deploy weather app from multi-agent system - %date% %time%"
if %errorlevel% neq 0 (
    echo Error: Git commit failed
    exit /b 1
)

echo Pushing to GitHub...
git push origin main
if %errorlevel% equ 0 (
    echo SUCCESS: Weather app deployed to GitHub!
    exit /b 0
) else (
    echo Trying master branch...
    git push origin master
    if %errorlevel% equ 0 (
        echo SUCCESS: Weather app deployed to GitHub (master)!
    else (
        echo ERROR: Failed to push to GitHub
        echo Please check your Git credentials and remote configuration
        exit /b 1
    )
)
