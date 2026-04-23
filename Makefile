.PHONY: install test lint typecheck format example clean build

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short --cov=trade_md --cov-report=term-missing

lint:
	ruff check src/ tests/

typecheck:
	mypy src/trade_md/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

example:
	trade-md lint examples/heritage-rsi-ema/TRADE.md
	trade-md explain examples/heritage-rsi-ema/TRADE.md
	trade-md compile --target freqtrade examples/heritage-rsi-ema/TRADE.md

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build: clean
	pip install build
	python -m build
