#!/bin/bash
# Deploy initialization script
# This script runs during deployment to set up the database and train the ML model

set -e  # Exit on error

echo "🚀 Starting deployment initialization..."

# 1. Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# 2. Initialize database
echo "🗄️  Initializing database..."
python scripts/init_db.py --reset --force

# 3. Seed initial data
echo "🌱 Seeding database with sample data..."
python scripts/seed_data.py

# 4. Seed initial data
echo "🌱 Seeding database with historical data..."
python scripts/seed_historical_data.py

# 5. Train ML model (if not exists or force retrain)
echo "🤖 Training ML model..."
if [ ! -f "models/demand_model.pkl" ] || [ "$FORCE_RETRAIN" = "true" ]; then
    python scripts/train_model.py
    echo "✅ Model trained successfully"
else
    echo "ℹ️  Using existing model (set FORCE_RETRAIN=true to retrain)"
fi

# 6. Verify setup
echo "🔍 Verifying setup..."
python -c "
import sys
from pathlib import Path
from src.core.database import get_db_session
from sqlalchemy import text

# Check database connection
try:
    with get_db_session() as db:
        result = db.execute(text('SELECT COUNT(*) FROM matches')).scalar()
        print(f'✅ Database: {result} matches found')
except Exception as e:
    print(f'❌ Database error: {e}')
    sys.exit(1)

# Check model file
model_path = Path('models/demand_model.pkl')
if model_path.exists():
    print(f'✅ ML Model: {model_path} ({model_path.stat().st_size} bytes)')
else:
    print('⚠️  ML Model not found - will use heuristic mode')

print('✅ Deployment initialization complete!')
"

echo "🎉 All initialization steps completed successfully!"
