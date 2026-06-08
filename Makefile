.PHONY: help install install-dev install-all test lint format clean build docker-build docker-run

help:
	@echo "DATA-AI Development Commands"
	@echo "============================"
	@echo "make install       Install core dependencies"
	@echo "make install-dev   Install with dev dependencies"
	@echo "make install-all   Install all optional dependencies"
	@echo "make test          Run tests"
	@echo "make lint          Run linting"
	@echo "make format        Format code"
	@echo "make clean         Clean build artifacts"
	@echo "make build         Build package"
	@echo "make docker-build  Build Docker image"
	@echo "make docker-run    Run Docker container"

install:
	pip install -e "."

install-dev:
	pip install -e ".[all]" pytest pytest-asyncio pytest-cov ruff

install-all:
	pip install -e ".[all]"

patch:
	python scripts/patch_fastapi_204.py

test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ -v --tb=short --cov=src/data_ai --cov-report=term-missing

lint:
	python -m ruff check src/ tests/

format:
	python -m ruff format src/ tests/

typecheck:
	python -m pyright src/ || true

clean:
	rm -rf build/ dist/ *.egg-info/ src/*.egg-info/ .pytest_cache/ .ruff_cache/ __pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build:
	python -m build

docker-build:
	DOCKER_BUILDKIT=1 docker build -t data-ai:latest .

docker-run:
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/config:/app/config \
		-e OPENAI_API_KEY=$(OPENAI_API_KEY) \
		data-ai:latest chat
