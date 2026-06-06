# =================================================================
# Makefile — Análisis de Listas de Espera NO GES
# Uso: make <target>
# =================================================================

.PHONY: help install install-dev test test-integration test-all pipeline

# Target por defecto
help:
	@echo ""
	@echo "  Análisis de Listas de Espera NO GES"
	@echo ""
	@echo "  make install          Instala dependencias de producción"
	@echo "  make install-dev      Instala dependencias de producción + tests"
	@echo "  make test             Tests unitarios (sin base de datos)"
	@echo "  make test-integration Tests de integración (requiere listas_espera_test)"
	@echo "  make test-all         Todos los tests"
	@echo "  make pipeline FILE=data/staging/2025_T1.xlsx"
	@echo "                        Ejecuta el pipeline para un archivo Excel"
	@echo ""

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	python -m pytest -m "not integration" -v

test-integration:
	python -m pytest tests/integration/ -m integration -v

test-all:
	python -m pytest -v

pipeline:
	@test -n "$(FILE)" || (echo "ERROR: especifica el archivo con FILE=ruta/al/archivo.xlsx"; exit 1)
	python pipeline/orchestration/pipeline_runner.py $(FILE)