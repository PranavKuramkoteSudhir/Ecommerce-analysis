PYTHON ?= python3.12

.PHONY: check test

check:
	$(PYTHON) scripts/check_foundation.py

test:
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py' -v
