FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        python3 \
        python3-pip \
        python3-gi \
        python3-gi-cairo \
        python3-cairo \
        gir1.2-gtk-4.0 \
        gir1.2-adw-1 \
        gir1.2-gtk-3.0 \
        policykit-1 \
        libnotify-bin \
        lm-sensors \
        systemd \
        debhelper \
        dh-python \
        pybuild-plugin-pyproject \
        python3-all \
        python3-setuptools \
        dpkg-dev \
        fakeroot \
        fonts-jetbrains-mono \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/home/ubuntu/.local/bin:${PATH}"

USER ubuntu
