#!/bin/bash

# Deploy script for Garant Bot

echo "🚀 Starting deployment process..."

# Check if required files exist
echo "📋 Checking required files..."
required_files=("bot.py" "config.py" "database.py" "requirements.txt" "Procfile")

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Error: Required file $file not found!"
        exit 1
    fi
done

echo "✅ All required files found"

# Check Python version
echo "🐍 Checking Python version..."
python_version=$(python3 --version 2>&1)
echo "Python version: $python_version"

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check database file
echo "💾 Checking database..."
if [ ! -f "garant_bot.db" ]; then
    echo "⚠️  Database file not found. Will be created on first run."
else
    echo "✅ Database file exists"
fi

# Environment variables check
echo "🔧 Checking environment variables..."
if [ -z "$BOT_TOKEN" ]; then
    echo "⚠️  BOT_TOKEN not set. Make sure to configure it in your hosting environment."
fi

if [ -z "$CRYPTOPAY_API_KEY" ]; then
    echo "⚠️  CRYPTOPAY_API_KEY not set. Make sure to configure it in your hosting environment."
fi

echo "✅ Deployment preparation complete!"
echo "📝 Next steps:"
echo "   1. Set environment variables in your hosting platform"
echo "   2. Upload all files to your hosting service"
echo "   3. Start the bot using: python start_bot.py"
echo ""
echo "🔗 Required environment variables:"
echo "   - BOT_TOKEN"
echo "   - CRYPTOPAY_API_KEY"
echo "   - CRYPTOPAY_WALLET_ID"
echo "   - EXTERNAL_EXCHANGE_WALLET_ADDRESS"
echo "   - ADMIN_IDS"
echo ""
echo "🎉 Ready for deployment!"