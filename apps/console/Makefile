.PHONY: test lint run web build-web

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	ruff check src tests
	mypy src

run:
	PYTHONPATH=src python3 -m sdlc_console.cli serve

web:
	cd web && npm run dev

build-web:
	cd web && npm run build
