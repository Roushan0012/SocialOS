#!/usr/bin/env bash
# ==============================================================================
# SocialOS Local Development Helper Script
# ==============================================================================
set -e

COMMAND="${1:-help}"

case "$COMMAND" in
  backend)
    echo "Starting FastAPI Backend..."
    cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ;;
  frontend)
    echo "Starting Next.js Frontend..."
    cd frontend && npm run dev
    ;;
  worker)
    echo "Starting Celery Worker..."
    cd backend && .venv/bin/celery -A app.workers.celery_app.celery_app worker -l info -Q default,publish_queue,analytics_queue,maintenance_queue
    ;;
  beat)
    echo "Starting Celery Beat..."
    cd backend && .venv/bin/celery -A app.workers.celery_app.celery_app beat -l info
    ;;
  test)
    echo "Running backend test suite..."
    cd backend && .venv/bin/pytest -v
    ;;
  lint)
    echo "Running frontend lint..."
    cd frontend && npm run lint
    ;;
  docker-up)
    echo "Starting Docker Compose services..."
    docker compose up -d
    ;;
  docker-down)
    echo "Stopping Docker Compose services..."
    docker compose down
    ;;
  *)
    echo "SocialOS Development CLI"
    echo "Usage: ./scripts/dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  backend     Start FastAPI backend server with hot-reload"
    echo "  frontend    Start Next.js frontend development server"
    echo "  worker      Start Celery background worker fleet"
    echo "  beat        Start Celery Beat periodic task scheduler"
    echo "  test        Run backend pytest test suite"
    echo "  lint        Run Next.js ESLint checker"
    echo "  docker-up   Start full Docker Compose development stack"
    echo "  docker-down Stop Docker Compose development stack"
    ;;
esac
