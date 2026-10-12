"""Reject unexpected managed-resource actions in reviewed Docker Host IAM plans.

Read terraform show -json from stdin. Do not print plan values or credentials.
"""

import argparse
import json
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("stage", choices=("default", "prepare", "migrate", "rollback"))
parser.add_argument("--includes-iam-creation", action="store_true")
args = parser.parse_args()
plan = json.load(sys.stdin)
if (
    not plan.get("format_version", "").startswith("1.")
    or "planned_values" not in plan
    or plan.get("errored", False)
    or plan.get("complete") is False
):
    raise SystemExit("FAIL: invalid, failed or incomplete plan")
if args.includes_iam_creation and args.stage != "migrate":
    parser.error("--includes-iam-creation is only for migration fixture checks")
prefix = "module.docker_host_iam[0]."
host_iam = {
    prefix + "aws_iam_role.docker_host",
    prefix + "aws_iam_role_policy_attachment.docker_host_ssm",
    prefix + "aws_iam_role_policy.docker_host_ecr_pull",
    prefix + "aws_iam_instance_profile.docker_host",
}
expected = {}
if args.stage == "prepare" or args.includes_iam_creation:
    expected.update({address: ["create"] for address in host_iam})
if args.stage in ("migrate", "rollback"):
    expected["aws_instance.docker_host"] = ["update"]
actual = {}
for item in plan.get("resource_changes", []):
    if item.get("mode") != "managed":
        continue
    address, change = item["address"], item["change"]
    actions = change["actions"]
    if actions == ["no-op"]:
        continue
    if "delete" in actions or change.get("replace_paths"):
        raise SystemExit("FAIL: destruction or replacement detected")
    actual[address] = actions
    if address == "aws_instance.docker_host" and actions == ["update"]:
        before, after = change["before"], change["after"]
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        if changed != {"iam_instance_profile"}:
            raise SystemExit("FAIL: Docker Host changes exceed its IAM profile")
        desired = "uptimeforge-dev-ec2-ssm-profile" if args.stage == "rollback" else "uptimeforge-dev-docker-host-profile"
        if after["iam_instance_profile"] != desired:
            raise SystemExit("FAIL: unexpected target profile")
if actual != expected:
    raise SystemExit("FAIL: managed-resource actions differ from the approved stage")
print("PASS: approved IAM stage; zero replacements and no unrelated resource changes")
