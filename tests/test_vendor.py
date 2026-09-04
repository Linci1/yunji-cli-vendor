import importlib.util
import io
import json
import os
import re
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
    def test_known_test_endpoint_is_rejected(self):
        endpoint = "https://yunji." + "huabeiapi.com"
        with self.assertRaisesRegex(MODULE.VendorError, "只允许连接云集正式环境"):
            MODULE.normalize_server_url(endpoint)

    def test_windows_launcher_supports_windows_python(self):
        launcher = (MODULE_PATH.parent / "yunji.cmd").read_text(encoding="utf-8")
        self.assertIn("py -3", launcher)
        self.assertIn("python ", launcher)
        self.assertIn("yunji_vendor.py", launcher)

    def test_release_package_has_sanitized_allowlist(self):
        package_script = MODULE_PATH.parents[1] / "tools" / "package_release.py"
        source = package_script.read_text(encoding="utf-8")
        self.assertIn('"scripts/yunji.cmd"', source)
        self.assertIn('"tools/install-windows.ps1"', source)
        self.assertNotIn("git.in.", source.replace('"internal Git service": re.compile(r"git\\.in\\.", re.I)', ""))

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
                "work-hours-list", "work-hours-detail", "work-hours-submit",
                "work-hours-update", "work-hours-check", "process-trace",
                "materials-by-order", "material-download",
            },
        )

    def test_full_guides_cover_vendor_surface(self):
        parser = MODULE.build_parser()
        command_action = next(action for action in parser._actions if action.dest == "command")
        commands = set(command_action.choices)
        cli_guide = (MODULE_PATH.parents[1] / "docs" / "vendor-cli-2.5-guide.md").read_text(encoding="utf-8")
        self.assertEqual({name for name in commands if name not in cli_guide}, set())

        source = MODULE_PATH.read_text(encoding="utf-8")
        api_guide = (MODULE_PATH.parents[1] / "docs" / "vendor-api-2.5-guide.md").read_text(encoding="utf-8")
        endpoints = {
            re.sub(r"\?.*$", "", endpoint).replace("{args.id}", "{id}").replace("{query}", "")
            for endpoint in re.findall(r"/api/admin/[A-Za-z0-9_?=&${}/.-]+", source)
        }
        self.assertEqual({endpoint for endpoint in endpoints if endpoint not in api_guide}, set())

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

    def test_server_is_fixed_to_production(self):
        with self.assertRaises(MODULE.VendorError):
            MODULE.normalize_server_url("http://example.invalid")
        with self.assertRaises(MODULE.VendorError):
            MODULE.normalize_server_url("https://user:pass@example.invalid")
        with self.assertRaisesRegex(MODULE.VendorError, "只允许连接云集正式环境"):
            MODULE.normalize_server_url("https://example.invalid/")
        self.assertEqual(MODULE.normalize_server_url(MODULE.DEFAULT_BASE_URL), MODULE.DEFAULT_BASE_URL)

    def test_server_defaults_to_builtin_production(self):
        with tempfile.TemporaryDirectory() as directory:
            old_file = MODULE.SERVER_FILE
            try:
                MODULE.SERVER_FILE = Path(directory) / "missing-server-url"
                with patch.dict(MODULE.os.environ, {}, clear=True):
                    self.assertEqual(MODULE.configured_server(), (MODULE.DEFAULT_BASE_URL, "builtin"))
            finally:
                MODULE.SERVER_FILE = old_file

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

    def test_work_hours_submit_requires_yes(self):
        args = type("Args", (), {
            "command": "work-hours-submit", "requirement_order_id": 3033,
            "order_serial_no": "", "user_id": 112, "date": "2026-09-02",
            "work_hours": 8, "remark": "", "yes": False, "compact": True,
        })()
        with patch.object(MODULE, "require_role", return_value={}), patch.object(MODULE, "api_request") as request:
            self.assertEqual(MODULE.command_work_hours_submit(args), 2)
            request.assert_not_called()

    def test_work_hours_submit_uses_engineer_id(self):
        args = type("Args", (), {
            "command": "work-hours-submit", "requirement_order_id": 3033,
            "order_serial_no": "", "user_id": 112, "date": "2026-09-02",
            "work_hours": 8, "remark": "现场服务", "yes": True, "compact": True,
        })()
        with patch.object(MODULE, "require_role", return_value={}), patch.object(MODULE, "api_request", return_value={"data": None}) as request, patch("sys.stdout", io.StringIO()):
            self.assertEqual(MODULE.command_work_hours_submit(args), 0)
        request.assert_called_once_with(
            "/api/admin/security-product/work-record/submit",
            method="POST",
            body={"requirementOrderId": 3033, "orderSerialNo": "", "userId": 112, "date": "2026-09-02", "workHours": 8, "remark": "现场服务"},
        )

    def test_employee_cannot_check_purchase_order_work_hours(self):
        args = type("Args", (), {"command": "work-hours-check", "purchase_order_id": 638, "requirement_order_id": None, "compact": True})()
        with patch.object(MODULE, "require_role", side_effect=MODULE.VendorError("当前账号不是此命令允许的供应商角色。")), patch.object(MODULE, "api_request") as request:
            with self.assertRaises(MODULE.VendorError):
                MODULE.command_work_hours_check(args)
            request.assert_not_called()

    def test_purchase_response_includes_work_hour_reason(self):
        args = type("Args", (), {
            "command": "partner-purchase-respond", "id": 638, "purchase_amount": 1000,
            "tax_rate": 0.06, "user_ids": [112], "work_hour_error_reason": "工作超出预估时长",
            "work_hour_error_reason_detail": "临时增加工作", "yes": True, "compact": True,
        })()
        with patch.object(MODULE, "require_role", return_value={}), patch.object(MODULE, "api_request", return_value={"data": None}) as request, patch("sys.stdout", io.StringIO()):
            self.assertEqual(MODULE.command_purchase_respond(args), 0)
        request.assert_called_once_with(
            "/api/admin/purchase-order/partner_respond",
            method="POST",
            body={"orderId": 638, "purchaseAmount": 1000, "taxRate": 0.06, "userIds": [112], "workHourErrorReason": "工作超出预估时长", "workHourErrorReasonDetail": "临时增加工作"},
        )

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
