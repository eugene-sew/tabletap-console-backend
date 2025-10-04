#!/bin/bash

# TableTap Console Backend Development Script

set -e

echo "🚀 Starting TableTap Console Backend Development Environment"
echo "📦 This will start PostgreSQL, Redis, and Django with volume mounts"

# Build and start the development environment
echo "🔨 Building development containers..."
docker-compose -f docker-compose.dev.yml build

echo "🎯 Starting development services..."
echo "   - PostgreSQL: localhost:5435"
echo "   - Redis: localhost:6379"
echo "   - Django API: localhost:3001"
echo ""
docker-compose -f docker-compose.dev.yml up

# Cleanup function
cleanup() {
    echo "🧹 Stopping development services..."
    docker-compose -f docker-compose.dev.yml down
}

# Set trap to cleanup on script exit
trap cleanup EXIT
