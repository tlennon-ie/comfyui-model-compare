#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick push script for comfyui-model-compare repository
    
.DESCRIPTION
    This script helps you push changes to GitHub with proper message formatting
    and provides status feedback throughout the process.
    
.EXAMPLE
    .\push-to-github.ps1
#>

# Set the working directory
Set-Location "e:\AI\Comf\ComfyUI\custom_nodes\comfyui-model-compare"

# Check if git is installed
try {
    $null = git --version
} catch {
    Write-Host "Error: Git is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Show current status
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ComfyUI Model Compare - Git Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

git status

Write-Host ""
$continue = Read-Host "Do you want to push these changes? (y/n)"

if ($continue -ne "y" -and $continue -ne "Y") {
    Write-Host "Push cancelled." -ForegroundColor Yellow
    exit 0
}

# Get commit message
Write-Host ""
Write-Host "Enter commit message (e.g., 'fix: Update grid layout algorithm'):" -ForegroundColor Cyan
$message = Read-Host "Message"

# Validate message
if ([string]::IsNullOrWhiteSpace($message)) {
    Write-Host "Error: Commit message cannot be empty" -ForegroundColor Red
    exit 1
}

# Add all changes
Write-Host ""
Write-Host "Staging changes..." -ForegroundColor Yellow
git add .

# Check if there are changes to commit
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "No changes to commit." -ForegroundColor Yellow
    exit 0
}

# Commit
Write-Host "Committing changes..." -ForegroundColor Yellow
git commit -m "$message"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to commit changes" -ForegroundColor Red
    exit 1
}

# Push to GitHub
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "SUCCESS! Changes pushed to GitHub" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "View your repository at:" -ForegroundColor Cyan
    Write-Host "https://github.com/tlennon-ie/comfyui-model-compare" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to push changes" -ForegroundColor Red
    Write-Host "Please check your GitHub credentials" -ForegroundColor Red
    exit 1
}
