# =============================================================================
# Resync Quick Setup with UV (Windows)
# =============================================================================
# Sets up complete development environment in seconds
# =============================================================================

Write-Host "🚀 Resync Setup with UV" -ForegroundColor Cyan
Write-Host "=======================" -ForegroundColor Cyan
Write-Host ""

# Check if uv is installed
$uvInstalled = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvInstalled) {
    Write-Host "📦 Installing uv..." -ForegroundColor Yellow
    
    irm https://astral.sh/uv/install.ps1 | iex
    
    Write-Host "✅ uv installed successfully" -ForegroundColor Green
} else {
    Write-Host "✅ uv already installed: $(uv --version)" -ForegroundColor Green
}

Write-Host ""
Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow

# Install all dependencies (includes dev)
uv sync

Write-Host ""
Write-Host "✅ Dependencies installed!" -ForegroundColor Green
Write-Host ""
Write-Host "🎯 Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # Run development server (with hot reload):" -ForegroundColor White
Write-Host "  uv run uvicorn resync.main:app --reload" -ForegroundColor Gray
Write-Host ""
Write-Host "  # Run tests:" -ForegroundColor White
Write-Host "  uv run pytest" -ForegroundColor Gray
Write-Host ""
Write-Host "  # Format code:" -ForegroundColor White
Write-Host "  uv run black ." -ForegroundColor Gray
Write-Host ""
Write-Host "  # Lint code:" -ForegroundColor White
Write-Host "  uv run ruff check ." -ForegroundColor Gray
Write-Host ""
Write-Host "🎉 Setup complete! Happy coding!" -ForegroundColor Green
