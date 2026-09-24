.PHONY: help build up down restart logs shell migrate makemigrations createsuperuser test clean

help:
	@echo "PhotoGear Backend - Docker Commands"
	@echo "===================================="
	@echo ""
	@echo "🐳 Docker Commands:"
	@echo "make build          - Build Docker images"
	@echo "make up             - Start all services"
	@echo "make down           - Stop all services"
	@echo "make restart        - Restart all services"
	@echo "make logs           - View logs (all services)"
	@echo "make logs-web       - View web service logs"
	@echo "make logs-db        - View database logs"
	@echo ""
	@echo "🗄️  Database Commands:"
	@echo "make migrate        - Run database migrations"
	@echo "make makemigrations - Create new migrations"
	@echo "make db-backup      - Backup database"
	@echo "make db-shell       - Open PostgreSQL shell"
	@echo ""
	@echo "🔧 Development Commands:"
	@echo "make shell          - Open Django shell"
	@echo "make bash           - Open bash in web container"
	@echo "make createsuperuser- Create Django superuser"
	@echo "make test           - Run tests"
	@echo "make collectstatic  - Collect static files"
	@echo ""
	@echo "✨ Code Quality Commands:"
	@echo "make setup-dev      - Install dev dependencies & pre-commit hooks"
	@echo "make format         - Format code with Black & isort"
	@echo "make lint           - Run flake8 linter"
	@echo "make type-check     - Run mypy type checker"
	@echo "make security-check - Run bandit security scanner"
	@echo "make pre-commit     - Run all pre-commit hooks"
	@echo "make code-quality   - Run all code quality checks"
	@echo ""
	@echo "🧹 Cleanup:"
	@echo "make clean          - Stop and remove volumes (WARNING: deletes data)"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-web:
	docker compose logs -f web

logs-db:
	docker compose logs -f db

shell:
	docker compose exec web python manage.py shell

bash:
	docker compose exec web bash

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

createsuperuser:
	docker compose exec web python manage.py createsuperuser

test:
	docker compose exec web python manage.py test

clean:
	docker compose down -v

db-backup:
	docker compose exec db pg_dump -U photogear_user photogear > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Database backed up to backup_$$(date +%Y%m%d_%H%M%S).sql"

db-shell:
	docker compose exec db psql -U photogear_user -d photogear

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

# Code Quality Commands
setup-dev:
	docker compose exec web bash -c "pip install -e '.[dev]' && pre-commit install"

format:
	docker compose exec web black . --line-length 120 --exclude migrations
	docker compose exec web isort . --profile black

lint:
	docker compose exec web flake8 . --max-line-length=120 --extend-ignore=E203,W503 --exclude=migrations,staticfiles,.venv,venv

type-check:
	docker compose exec web mypy . --ignore-missing-imports

security-check:
	docker compose exec web bandit -r . -c pyproject.toml

pre-commit:
	docker compose exec web pre-commit run --all-files

code-quality: format lint type-check security-check
	@echo "All code quality checks complete!"
