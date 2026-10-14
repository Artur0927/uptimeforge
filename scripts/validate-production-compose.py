"""Check the resolved production Compose contract without printing credentials."""

import ipaddress
import json
import re
import sys

config = json.load(sys.stdin)
services = config["services"]
api, worker, db = (services[name] for name in ("api", "worker", "db"))
image = api["image"]
if image != worker["image"] or not re.fullmatch(
    r"[0-9]{12}\.dkr\.ecr\.eu-north-1\.amazonaws\.com/uptimeforge-api:sha-[0-9a-f]{40}",
    image,
):
    raise SystemExit("FAIL: API and Worker require the same SHA-tagged UptimeForge ECR image")
if db.get("ports"):
    raise SystemExit("FAIL: PostgreSQL must not publish a host port")
ports = api["ports"]
if len(ports) != 1 or ports[0].get("host_ip") != "10.20.2.23":
    raise SystemExit("FAIL: API must bind only to the expected private Docker Host address")
try:
    proxy_ip = ipaddress.ip_address(api["environment"]["FORWARDED_ALLOW_IPS"])
except (KeyError, ValueError):
    raise SystemExit("FAIL: API proxy trust requires one explicit private Nginx IP") from None
if (
    proxy_ip.version != 4 or not proxy_ip.is_private or proxy_ip.is_loopback
    or proxy_ip.is_link_local or proxy_ip.is_unspecified or proxy_ip.is_multicast or proxy_ip.is_reserved
):
    raise SystemExit("FAIL: API proxy trust requires one explicit private Nginx IP")
if not config["volumes"]["pgdata"].get("external"):
    raise SystemExit("FAIL: PostgreSQL requires an explicitly selected existing volume")
for service in (api, worker):
    if not service.get("read_only") or "ALL" not in service.get("cap_drop", []):
        raise SystemExit("FAIL: Application containers require read-only filesystems and dropped caps")
    if "healthcheck" not in service or not service.get("mem_limit"):
        raise SystemExit("FAIL: Application containers require health checks and memory limits")
if services["migrate"].get("profiles") != ["tools"]:
    raise SystemExit("FAIL: Migrations must be explicitly invoked through the tools profile")
print("PASS: production Compose image, network, storage and container constraints")
