#!/bin/bash
# First boot: install Nginx and expose only a simple HTTP test page.
# Reverse proxy to the private FastAPI host and TLS are next-phase tasks.
set -euxo pipefail
dnf install -y nginx
cat >/usr/share/nginx/html/index.html <<'HTML'
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>UptimeForge</title></head>
<body><h1>UptimeForge: Nginx is up</h1><p>Private API connection comes next.</p></body>
</html>
HTML
systemctl enable --now nginx
