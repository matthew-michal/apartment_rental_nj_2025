#!/bin/bash
echo "🏠 Setting up apartment rental ML pipeline..."

if command -v pipenv &> /dev/null; then
    echo "📦 Using Pipenv..."
    if [ -f Pipfile ]; then
        pipenv install
    else
        pipenv install -r requirements.txt
    fi
    echo "🎯 Activate: pipenv shell"
    echo "🚀 Deploy: pipenv run ./deployment/deploy.sh"
else
    echo "📦 Using pip..."
    echo "💡 Install pipenv: pip install pipenv"
    echo "🚀 Deploy: ./deployment/deploy.sh"
fi
