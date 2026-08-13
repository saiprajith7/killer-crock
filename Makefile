# BOSS-Sentinel convenience targets
.PHONY: all build deb clean install-deps

all: build

build:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j$$(nproc)

deb:
	./packaging/build-deb.sh

clean:
	rm -rf build dist debian/boss-sentinel

install-deps:
	sudo apt-get install -y build-essential cmake pkg-config g++ \
	  libgtkmm-4.0-dev libglibmm-2.68-dev libgtk-4-dev \
	  python3 policykit-1 fakeroot dpkg-dev
