#!/bin/bash
# Test runner script for both frontend and backend

echo "🧪 Running Test Suites"
echo "======================"

# Backend tests
echo ""
echo "📦 Backend Tests (pytest)"
echo "-------------------------"
cd apps/api
if command -v pytest &> /dev/null; then
    pytest -v
else
    echo "⚠️  pytest not found. Install with: pip install pytest pytest-asyncio pytest-cov httpx"
fi
cd ../..

# Frontend tests
echo ""
echo "🌐 Frontend Tests (Jest)"
echo "-------------------------"
cd apps/web
if command -v npm &> /dev/null; then
    if [ ! -d "node_modules" ]; then
        echo "📥 Installing dependencies..."
        npm install
    fi
    npm test -- --passWithNoTests
else
    echo "⚠️  npm not found. Please install Node.js and npm."
fi
cd ../..

echo ""
echo "✅ Test run complete!"

