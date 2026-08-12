.PHONY: run run-once test deb clean

run:
	PYTHONPATH=src python3 -m bossoptimize

run-once:
	PYTHONPATH=src python3 -m bossoptimize --once

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

deb:
	bash packaging/build-deb.sh

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pybuild debian/boss-optimize debian/.debhelper debian/files debian/*.substvars
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
