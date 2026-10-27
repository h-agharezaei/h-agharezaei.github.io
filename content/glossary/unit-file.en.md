+++
title = "Unit file"
summary = "A small INI-like text file that tells systemd how to run or schedule one thing."
category = "Linux"
related = ["systemd"]
posts = ["linux-systemd-units-timers"]
+++

Names end with the unit type: `.service`, `.timer`, `.socket`, `.target`, `.mount`, `.path`. Sections such as `[Unit]`, `[Service]` and `[Install]` hold the settings. After editing one you run `systemctl daemon-reload`.
