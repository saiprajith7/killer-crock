.PHONY: install run run-sim test deb clean lint

PREFIX ?= /usr
DESTDIR ?=

install:
	python3 -m pip install --break-system-packages -e .
	install -d $(DESTDIR)$(PREFIX)/libexec/vitaheal
	install -m 0755 scripts/vitaheal-helper $(DESTDIR)$(PREFIX)/libexec/vitaheal/vitaheal-helper
	install -d $(DESTDIR)$(PREFIX)/share/applications
	install -m 0644 data/desktop/vitaheal.desktop $(DESTDIR)$(PREFIX)/share/applications/
	install -d $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
	install -m 0644 data/icons/vitaheal.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/vitaheal.svg
	install -d $(DESTDIR)$(PREFIX)/share/polkit-1/actions
	install -m 0644 data/polkit/org.vitaheal.policy $(DESTDIR)$(PREFIX)/share/polkit-1/actions/
	install -d $(DESTDIR)$(PREFIX)/lib/systemd/user
	install -m 0644 data/systemd/vitaheal-daemon.service $(DESTDIR)$(PREFIX)/lib/systemd/user/
	install -d $(DESTDIR)/etc/xdg/autostart
	install -m 0644 data/desktop/vitaheal-daemon.desktop $(DESTDIR)/etc/xdg/autostart/

run:
	PYTHONPATH=src python3 -m vitaheal

run-sim:
	PYTHONPATH=src python3 -m vitaheal --simulate-issue memory

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

deb:
	bash packaging/build-deb.sh

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pybuild debian/vitaheal debian/.debhelper debian/files debian/*.substvars debian/*.debhelper.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

lint:
	python3 -m compileall -q src scripts
