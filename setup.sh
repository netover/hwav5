#!/bin/bash
# =============================================================================
# Resync Quick Setup with UV
# =============================================================================
# Sets up complete development environment in seconds
# =============================================================================

set -e

echo "🚀 Resync Setup with UV"
echo "======================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "darwin"* ]]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Add to PATH for current session
        export PATH="$HOME/.cargo/bin:$PATH"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    fi
    
    echo "✅ uv installed successfully"
else
    echo "✅ uv already installed: $(uv --version)"
fi

echo ""
echo "📦 Installing dependencies..."

# Install all dependencies (includes dev)
uv sync

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "🎯 Next steps:"
echo ""
echo "  # Run development server (with hot reload):"
echo "  uv run uvicorn resync.main:app --reload"
echo ""
echo "  # Run tests:"
echo "  uv run pytest"
echo ""
echo "  # Format code:"
echo "  uv run black ."
echo ""
echo "  # Lint code:"
echo "  uv run ruff check ."
echo ""
echo "  # Interactive Python (with project loaded):"
echo "  uv run ipython"
echo ""
echo "🎉 Setup complete! Happy coding!"
