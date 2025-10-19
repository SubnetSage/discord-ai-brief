#!/bin/bash

# Discord AI Daily - Python Server Startup Script

echo "🚀 Starting Discord AI Daily Python Server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Run the Python server
echo "✅ Starting Flask server on http://localhost:8000"
python daily_ai_summary.py
