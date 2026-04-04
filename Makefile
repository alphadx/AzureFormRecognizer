# Makefile para Document Processor API

.PHONY: help install test lint format clean docker-build docker-up docker-down run demo-up demo-up-build

# Variables
PYTHON := python3
PIP := pip3
DEMO ?= 0
COMPOSE_PROFILE_ARGS :=

ifeq ($(DEMO),1)
COMPOSE_PROFILE_ARGS := --profile demo
endif

DOCKER_COMPOSE := docker compose -f docker/docker-compose.yml $(COMPOSE_PROFILE_ARGS)

# Colores
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

help: ## Muestra esta ayuda
	@echo "$(BLUE)Document Processor API - Comandos disponibles:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# ============================================
# Desarrollo Local
# ============================================

install: ## Instala dependencias de desarrollo
	@echo "$(BLUE)Instalando dependencias...$(NC)"
	$(PIP) install -r requirements.txt

dev: ## Ejecuta el servidor en modo desarrollo
	@echo "$(BLUE)Iniciando servidor de desarrollo...$(NC)"
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run: ## Ejecuta el servidor en modo producción
	@echo "$(BLUE)Iniciando servidor...$(NC)"
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# ============================================
# Testing
# ============================================

test: ## Ejecuta todos los tests
	@echo "$(BLUE)Ejecutando tests...$(NC)"
	pytest

test-verbose: ## Ejecuta tests con verbose
	@echo "$(BLUE)Ejecutando tests (verbose)...$(NC)"
	pytest -v

test-coverage: ## Ejecuta tests con cobertura
	@echo "$(BLUE)Ejecutando tests con cobertura...$(NC)"
	pytest --cov=app --cov-report=term-missing --cov-report=html

test-auth: ## Ejecuta tests de autenticación
	@echo "$(BLUE)Ejecutando tests de autenticación...$(NC)"
	pytest tests/test_auth.py -v

test-processor: ## Ejecuta tests del procesador
	@echo "$(BLUE)Ejecutando tests del procesador...$(NC)"
	pytest tests/test_document_processor.py -v

test-api: ## Ejecuta tests de API
	@echo "$(BLUE)Ejecutando tests de API...$(NC)"
	pytest tests/test_api.py -v

# ============================================
# Docker
# ============================================

docker-build: ## Construye la imagen Docker
	@echo "$(BLUE)Construyendo imagen Docker...$(NC)"
	$(DOCKER_COMPOSE) build

docker-up: ## Inicia los contenedores
	@echo "$(BLUE)Iniciando contenedores (DEMO=$(DEMO))...$(NC)"
	$(DOCKER_COMPOSE) up -d

docker-up-build: ## Construye e inicia los contenedores
	@echo "$(BLUE)Construyendo e iniciando contenedores (DEMO=$(DEMO))...$(NC)"
	$(DOCKER_COMPOSE) up --build -d

docker-test: ## Ejecuta tests dentro de Docker usando el código del repo montado
	@echo "$(BLUE)Ejecutando tests dentro de Docker...$(NC)"
	docker compose -f docker/docker-compose.yml run --rm -v "$(PWD)":/workspace -w /workspace api pytest

demo-up: ## Inicia contenedores con web demo (equivale a DEMO=1)
	@echo "$(BLUE)Iniciando contenedores con DEMO...$(NC)"
	$(MAKE) docker-up DEMO=1

demo-up-build: ## Construye e inicia contenedores con web demo (equivale a DEMO=1)
	@echo "$(BLUE)Construyendo e iniciando contenedores con DEMO...$(NC)"
	$(MAKE) docker-up-build DEMO=1

docker-down: ## Detiene los contenedores
	@echo "$(BLUE)Deteniendo contenedores...$(NC)"
	$(DOCKER_COMPOSE) down

docker-logs: ## Muestra logs de los contenedores
	@echo "$(BLUE)Mostrando logs...$(NC)"
	$(DOCKER_COMPOSE) logs -f

docker-logs-api: ## Muestra logs solo de la API
	@echo "$(BLUE)Mostrando logs de API...$(NC)"
	$(DOCKER_COMPOSE) logs -f api

docker-restart: ## Reinicia los contenedores
	@echo "$(BLUE)Reiniciando contenedores...$(NC)"
	$(DOCKER_COMPOSE) restart

docker-clean: ## Elimina contenedores, volúmenes e imágenes
	@echo "$(YELLOW)Eliminando contenedores, volúmenes e imágenes...$(NC)"
	$(DOCKER_COMPOSE) down -v --rmi all

# ============================================
# Utilidades
# ============================================

lint: ## Ejecuta linter (flake8)
	@echo "$(BLUE)Ejecutando linter...$(NC)"
	flake8 app tests --max-line-length=120 --ignore=E501,W503

format: ## Formatea el código (black)
	@echo "$(BLUE)Formateando código...$(NC)"
	black app tests

format-check: ## Verifica formato del código
	@echo "$(BLUE)Verificando formato...$(NC)"
	black --check app tests

clean: ## Limpia archivos temporales
	@echo "$(YELLOW)Limpiando archivos temporales...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov build dist .eggs
	@echo "$(GREEN)Limpieza completada$(NC)"

# ============================================
# Testing de API
# ============================================

test-api-script: ## Ejecuta script de prueba Bash
	@echo "$(BLUE)Ejecutando script de prueba (Bash)...$(NC)"
	chmod +x scripts/test_api.sh
	./scripts/test_api.sh

test-api-python: ## Ejecuta script de prueba Python
	@echo "$(BLUE)Ejecutando script de prueba (Python)...$(NC)"
	python scripts/test_api.py

# ============================================
# Documentación
# ============================================

docs: ## Abre documentación Swagger
	@echo "$(GREEN)Documentación disponible en:$(NC)"
	@echo "  - Swagger UI: http://localhost:8000/docs"
	@echo "  - ReDoc:      http://localhost:8000/redoc"

# ============================================
# Configuración
# ============================================

setup: ## Configura el proyecto por primera vez
	@echo "$(BLUE)Configurando proyecto...$(NC)"
	cp .env.example .env
	@echo "$(YELLOW)Por favor, edita el archivo .env con tus credenciales$(NC)"
	@echo "$(GREEN)Configuración completada. Ejecuta 'make install' para instalar dependencias.$(NC)"

env: ## Muestra variables de entorno configuradas
	@echo "$(BLUE)Variables de entorno:$(NC)"
	@cat .env | grep -v "^#" | grep -v "^$$"

# ============================================
# Despliegue
# ============================================

deploy-check: ## Verifica que todo esté listo para desplegar
	@echo "$(BLUE)Verificando configuración...$(NC)"
	@echo "$(YELLOW)Verificando variables de entorno...$(NC)"
	@test -f .env && echo "  ✓ .env existe" || (echo "  ✗ .env no existe" && exit 1)
	@echo "$(YELLOW)Verificando tests...$(NC)"
	@make test > /dev/null 2>&1 && echo "  ✓ Tests pasan" || (echo "  ✗ Tests fallan" && exit 1)
	@echo "$(GREEN)✓ Todo listo para desplegar$(NC)"

.DEFAULT_GOAL := help
