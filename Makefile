.PHONY: install test test-all run fixture clean

install:
	pip install -r requirements-dev.txt

test:
	pytest -m "not slow"

test-all:
	pytest

run:
	streamlit run app.py

fixture:
	python scripts/fetch_spy_fixture.py

clean:
	rm -rf .pytest_cache .yfcache
	find . -type d -name __pycache__ -exec rm -rf {} +
