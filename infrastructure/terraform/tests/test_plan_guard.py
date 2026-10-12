"""Safety regression cases for managed-resource plan approval."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/verify-docker-host-iam-plan.py"
PREFIX = "module.docker_host_iam[0]."
IAM = [
    "aws_iam_role.docker_host",
    "aws_iam_role_policy_attachment.docker_host_ssm",
    "aws_iam_role_policy.docker_host_ecr_pull",
    "aws_iam_instance_profile.docker_host",
]
SHARED = "uptimeforge-dev-ec2-ssm-profile"
DEDICATED = "uptimeforge-dev-docker-host-profile"


def change(address, actions, before=None, after=None):
    return {"address": address, "mode": "managed", "change": {
        "actions": actions, "before": before or {}, "after": after or {},
    }}


def plan(changes):
    return {"format_version": "1.2", "complete": True,
            "planned_values": {}, "resource_changes": changes}


class PlanGuardTests(unittest.TestCase):
    def check(self, stage, value, success, extra=()):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), stage, *extra],
            input=json.dumps(value), text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_default_preserves_existing_stack(self):
        self.check("default", plan([change("aws_instance.nat", ["no-op"])]), True)
        self.check("default", plan([change("aws_instance.nat", ["update"])]), False)

    def test_preparation_requires_exact_four_iam_creates(self):
        value = plan([change(PREFIX + name, ["create"]) for name in IAM])
        self.check("prepare", value, True)
        for index in range(len(IAM)):
            broken = copy.deepcopy(value)
            broken["resource_changes"].pop(index)
            self.check("prepare", broken, False)

    def test_migration_only_updates_host_profile(self):
        before = {"iam_instance_profile": SHARED, "ami": "unchanged", "subnet_id": "unchanged"}
        after = {**before, "iam_instance_profile": DEDICATED}
        value = plan([change("aws_instance.docker_host", ["update"], before, after)])
        self.check("migrate", value, True)
        for key in ("ami", "subnet_id", "iam_instance_profile"):
            broken = copy.deepcopy(value)
            broken["resource_changes"][0]["change"]["after"][key] = "unexpected"
            self.check("migrate", broken, False)

    def test_fixture_with_iam_creation_is_explicit(self):
        value = plan([change(PREFIX + name, ["create"]) for name in IAM] + [
            change("aws_instance.docker_host", ["update"],
                   {"iam_instance_profile": SHARED}, {"iam_instance_profile": DEDICATED}),
        ])
        self.check("migrate", value, False)
        self.check("migrate", value, True, ("--includes-iam-creation",))

    def test_rollback_keeps_dedicated_iam_and_restores_shared_profile(self):
        value = plan([change(PREFIX + name, ["no-op"]) for name in IAM] + [
            change("aws_instance.docker_host", ["update"],
                   {"iam_instance_profile": DEDICATED}, {"iam_instance_profile": SHARED}),
        ])
        self.check("rollback", value, True)
        value["resource_changes"][0]["change"]["actions"] = ["delete"]
        self.check("rollback", value, False)

    def test_replacements_destruction_and_unrelated_resources_fail(self):
        for address in ("aws_instance.nat", "aws_instance.nginx", "aws_vpc.main",
                        "module.ecr.aws_ecr_repository.application", "aws_instance.docker_host"):
            for actions in (["delete", "create"], ["create", "delete"], ["delete"], ["update"]):
                with self.subTest(address=address, actions=actions):
                    self.check("default", plan([change(address, actions)]), False)

    def test_failed_incomplete_or_non_plan_input_fails(self):
        for value in ({}, {**plan([]), "errored": True}, {**plan([]), "complete": False}):
            self.check("default", value, False)


if __name__ == "__main__":
    unittest.main()
