.PHONY: install run run-sentinel run-once run-sim test deb deb-local clean lint

PREFIX ?= /usr
DESTDIR ?=

install:
	python3 -m pip install --break-system-packages -e .
	install -d $(DESTDIR)$(PREFIX)/libexec/boss-sentinel
	install -m 0755 scripts/vitaheal-helper $(DESTDIR)$(PREFIX)/libexec/boss-sentinel/boss-sentinel-helper
	install -d $(DESTDIR)$(PREFIX)/share/applications
	install -m 0644 data/desktop/vitaheal.desktop $(DESTDIR)$(PREFIX)/share/applications/boss-sentinel.desktop
	install -m 0644 data/desktop/boss-health.desktop $(DESTDIR)$(PREFIX)/share/applications/boss-health.desktop
	install -d $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
	install -m 0644 data/icons/vitaheal.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/boss-sentinel.svg
	install -m 0644 data/icons/boss-health.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/boss-health.svg
	install -d $(DESTDIR)$(PREFIX)/share/polkit-1/actions
	install -m 0644 data/polkit/org.vitaheal.policy $(DESTDIR)$(PREFIX)/share/polkit-1/actions/org.bosssentinel.policy
	install -d $(DESTDIR)$(PREFIX)/lib/systemd/user
	install -m 0644 data/systemd/vitaheal-daemon.service $(DESTDIR)$(PREFIX)/lib/systemd/user/boss-sentinel-daemon.service
	install -d $(DESTDIR)/etc/xdg/autostart
	install -m 0644 data/desktop/vitaheal-daemon.desktop $(DESTDIR)/etc/xdg/autostart/boss-sentinel-daemon.desktop
	install -d $(DESTDIR)/etc/boss-health
	install -m 0644 data/config/boss-health.conf $(DESTDIR)/etc/boss-health/boss-health.conf
	install -d $(DESTDIR)$(PREFIX)/share/cinnamon/applets/boss-health@boss
	install -m 0644 data/cinnamon/applets/boss-health@boss/applet.js $(DESTDIR)$(PREFIX)/share/cinnamon/applets/boss-health@boss/applet.js
	install -m 0644 data/cinnamon/applets/boss-health@boss/metadata.json $(DESTDIR)$(PREFIX)/share/cinnamon/applets/boss-health@boss/metadata.json
	install -m 0644 data/icons/boss-health.svg $(DESTDIR)$(PREFIX)/share/cinnamon/applets/boss-health@boss/icon.svg

run:
	PYTHONPATH=src python3 -m boss_health

run-sentinel:
	PYTHONPATH=src python3 -m vitaheal

run-once:
	PYTHONPATH=src python3 -m boss_health --once

run-sim:
	PYTHONPATH=src python3 -m vitaheal --simulate-issue memory

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

deb:
	bash packaging/build-deb.sh

deb-local:
	bash packaging/build-local-deb.sh

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pybuild debian/vitaheal debian/boss-sentinel debian/.debhelper debian/files debian/*.substvars debian/*.debhelper.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

lint:
	python3 -m compileall -q src scripts
