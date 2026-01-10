# PowerShell test runner script for both frontend and backend

Write-Host "🧪 Running Test Suites" -ForegroundColor Cyan
Write-Host "======================" -ForegroundColor Cyan

# Backend tests
Write-Host ""
Write-Host "📦 Backend Tests (pytest)" -ForegroundColor Yellow
Write-Host "-------------------------" -ForegroundColor Yellow
Set-Location "apps\api"
if (Get-Command pytest -ErrorAction SilentlyContinue) {
    pytest -v
} else {
    Write-Host "⚠️  pytest not found. Install with: pip install pytest pytest-asyncio pytest-cov httpx" -ForegroundColor Red
}
Set-Location "..\.."

# Frontend tests
Write-Host ""
Write-Host "🌐 Frontend Tests (Jest)" -ForegroundColor Yellow
Write-Host "-------------------------" -ForegroundColor Yellow
Set-Location "apps\web"
if (Get-Command npm -ErrorAction SilentlyContinue) {
    if (-not (Test-Path "node_modules")) {
        Write-Host "📥 Installing dependencies..." -ForegroundColor Cyan
        npm install
    }
    npm test -- --passWithNoTests
} else {
    Write-Host "⚠️  npm not found. Please install Node.js and npm." -ForegroundColor Red
}
Set-Location "..\.."

Write-Host ""
Write-Host "✅ Test run complete!" -ForegroundColor Green

