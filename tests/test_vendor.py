import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "yunji_vendor.py"
SPEC = importlib.util.spec_from_file_location("yunji_vendor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class VendorCliTest(unittest.TestCase):
    def test_parser_exposes_only_vendor_commands(self):
        parser = MODULE.build_parser()
        choices = next(action.choices for action in parser._actions if action.dest == "command")
        self.assertEqual(
            set(choices),
            {
                "config", "auth", "whoami",
                "partner-employee-list", "partner-employee-detail", "partner-employee-create",
                "partner-employee-update", "partner-employee-switch", "partner-employee-tag",
                "requirement-order-list", "requirement-order-detail", "requirement-order-approve",
                "requirement-order-reject", "partner-purchase-list", "partner-purchase-detail",
                "partner-purchase-response-info", "partner-purchase-respond",
                "materials-by-order", "material-download",
            },
        )

    def test_login_has_no_token_or_stdin_argument(self):
        parser = MODULE.build_parser()
        auth = next(action.choices["auth"] for action in parser._actions if action.dest == "command")
        auth_choices = next(action.choices for action in auth._actions if action.dest == "auth_command")
        login_flags = {flag for action in auth_choices["login"]._actions for flag in action.option_strings}
        self.assertNotIn("--token", login_flags)
        self.assertNotIn("--stdin", login_flags)

    def test_internal_role_is_rejected(self):
        with patch.object(MODULE, "api_request", return_value={"data": {"id": 1, "roles": ["admin"]}}):
            with self.assertRaises(MODULE.VendorError):
                MODULE.require_role(MODULE.ROLE_ADMIN)

    def test_supplier_admin_is_allowed(self):
        payload = {"data": {"id": 2, "nickname": "供应商用户", "username": "private-login", "isPartnerAdmin": True}}
        with patch.object(MODULE, "api_request", return_value=payload):
            identity = MODULE.require_role(MODULE.ROLE_ADMIN)
        self.assertEqual(identity["roles"], [MODULE.ROLE_ADMIN])
        self.assertNotIn("username", identity)

    def test_supplier_employee_cannot_run_admin_command(self):
        args = type("Args", (), {"page": 1, "limit": 20, "id": None, "name": "", "phone": "", "level": "", "compact": True, "command": "partner-employee-list"})()
        employee = {"id": 3, "roles": [MODULE.ROLE_EMPLOYEE]}
        with patch.object(MODULE, "current_identity", return_value=employee), patch.object(MODULE, "api_request") as request:
            with self.assertRaises(MODULE.VendorError):
                MODULE.command_employee_list(args)
            request.assert_not_called()

    def test_whoami_does_not_output_username_or_token(self):
        args = type("Args", (), {"compact": True})()
        identity = {"id": 2, "name": "供应商用户", "supplierId": 9, "roles": [MODULE.ROLE_ADMIN]}
        output = io.StringIO()
        with patch.object(MODULE, "require_role", return_value=identity), patch("sys.stdout", output):
            MODULE.command_whoami(args)
        payload = json.loads(output.getvalue())
        self.assertNotIn("username", payload["identity"])
        self.assertNotIn("token", json.dumps(payload).lower())

    def test_server_requires_https_and_no_credentials(self):
        with self.assertRaises(MODULE.VendorError):
            MODULE.normalize_server_url("http://example.invalid")
        with self.assertRaises(MODULE.VendorError):
            MODULE.normalize_server_url("https://user:pass@example.invalid")
        self.assertEqual(MODULE.normalize_server_url("https://example.invalid/"), "https://example.invalid")

    def test_private_files_use_restricted_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            old_dir = MODULE.CONFIG_DIR
            try:
                MODULE.CONFIG_DIR = Path(directory) / "config"
                path = MODULE.CONFIG_DIR / "secret"
                MODULE.save_private(path, "value")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(MODULE.CONFIG_DIR.stat().st_mode & 0o777, 0o700)
            finally:
                MODULE.CONFIG_DIR = old_dir

    def test_write_requires_yes_before_api_call(self):
        args = type("Args", (), {"yes": False, "compact": True, "command": "requirement-order-approve", "id": 1})()
        with patch.object(MODULE, "require_role", return_value={}), patch.object(MODULE, "api_request") as request:
            self.assertEqual(MODULE.command_order_action(args), 2)
            request.assert_not_called()

    def test_direct_download_never_calls_credential_endpoint(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("download_credential", source)
        self.assertNotIn("batch_download_credentials", source)

    def test_install_in_isolated_directories(self):
        root = MODULE_PATH.parents[1]
        with tempfile.TemporaryDirectory() as directory:
            install_root = Path(directory) / "root"
            bin_dir = Path(directory) / "bin"
            subprocess.run(
                ["bash", str(root / "install.sh"), "--install-root", str(install_root), "--bin-dir", str(bin_dir)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            executable = bin_dir / "yunji"
            result = subprocess.run([str(executable), "--help"], check=True, capture_output=True, text=True)
            self.assertIn("云集供应商命令行工具", result.stdout)


if __name__ == "__main__":
    unittest.main()
