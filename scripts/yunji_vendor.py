#!/usr/bin/env python3
"""Minimal Yunji CLI for suppliers and supplier employees."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


CONFIG_DIR = Path(
    os.environ.get("YUNJI_VENDOR_CONFIG_DIR", Path.home() / ".config" / "yunji-cli-vendor")
).expanduser()
TOKEN_FILE = CONFIG_DIR / "access-token"
SERVER_FILE = CONFIG_DIR / "server-url"
DEFAULT_BASE_URL = "https://yunji.chaitin.cn"
__version__ = "2.5.0"

ROLE_ADMIN = "supplier-admin"
ROLE_EMPLOYEE = "supplier-employee"


class VendorError(RuntimeError):
    pass


class ChineseArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, f"{self.prog}: 参数错误：{message}\n请运行 `{self.prog} --help` 查看用法。\n")


def print_payload(payload: Any, compact: bool = False) -> None:
    indent = None if compact else 2
    print(json.dumps(payload, ensure_ascii=False, indent=indent, separators=(",", ":") if compact else None))


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)


def configured_token() -> tuple[str, str]:
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "", ""
    return (token, str(TOKEN_FILE)) if token else ("", "")


def configured_server() -> tuple[str, str]:
    env_url = os.environ.get("YUNJI_VENDOR_BASE_URL", "").strip()
    if env_url:
        return normalize_server_url(env_url), "env:YUNJI_VENDOR_BASE_URL"
    try:
        value = SERVER_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return DEFAULT_BASE_URL, "builtin"
    return (normalize_server_url(value), str(SERVER_FILE)) if value else (DEFAULT_BASE_URL, "builtin")


def normalize_server_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urllib_parse.urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise VendorError("服务地址必须是未包含账号密码的 HTTPS 地址。")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise VendorError("服务地址只能包含协议、域名和可选端口，不能包含路径、查询或片段。")
    if raw != DEFAULT_BASE_URL:
        raise VendorError("正式供应商 CLI 只允许连接云集正式环境，请移除服务地址覆盖。")
    return DEFAULT_BASE_URL


def save_private(path: Path, value: str) -> None:
    ensure_config_dir()
    path.write_text(value.strip() + "\n", encoding="utf-8")
    path.chmod(0o600)


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    paths = ssl.get_default_verify_paths()
    if paths.cafile and Path(paths.cafile).is_file():
        return context
    try:
        import certifi  # type: ignore[import-not-found]
    except ImportError:
        return context
    return ssl.create_default_context(cafile=certifi.where())


def auth_header(token: str) -> str:
    raw = token.strip()
    return raw if raw.startswith("Bearer ") else f"Bearer {raw}"


def api_request(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    body_format: str = "json",
    token: str | None = None,
) -> dict[str, Any]:
    server, _ = configured_server()
    if token is None:
        token, _ = configured_token()
    if not token:
        raise VendorError("尚未登录。请先运行 `yunji auth login`。")

    url = f"{server}{path if path.startswith('/') else '/' + path}"
    headers = {"Authorization": auth_header(token), "Accept": "application/json,text/plain,*/*"}
    payload: bytes | None = None
    if method.upper() not in {"GET", "HEAD"}:
        clean = {key: value for key, value in (body or {}).items() if value not in (None, "")}
        if body_format == "form":
            headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
            payload = urllib_parse.urlencode(clean, doseq=True).encode("utf-8")
        else:
            headers["Content-Type"] = "application/json;charset=UTF-8"
            payload = json.dumps(clean, ensure_ascii=False).encode("utf-8")

    request = urllib_request.Request(url, data=payload, headers=headers, method=method.upper())
    try:
        with urllib_request.urlopen(request, timeout=30, context=ssl_context()) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code in (401, 403):
            raise VendorError(f"当前身份未通过服务端权限校验（HTTP {exc.code}）。") from exc
        if exc.code == 404:
            raise VendorError("对象不存在，或当前身份无权查看该对象。") from exc
        raise VendorError(f"服务请求失败（HTTP {exc.code}）：{text}") from exc
    except urllib_error.URLError as exc:
        raise VendorError(f"无法连接供应商服务：{exc.reason}") from exc

    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise VendorError("服务返回了无法解析的数据。") from exc
    if isinstance(data, dict) and data.get("success") is False:
        raise VendorError(str(data.get("message") or "服务端拒绝了本次操作。"))
    return data if isinstance(data, dict) else {"data": data}


def unwrap(payload: dict[str, Any]) -> Any:
    if "data" in payload:
        return payload["data"]
    return payload


def identity_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    user = unwrap(payload)
    if not isinstance(user, dict):
        raise VendorError("当前用户接口未返回有效身份。")
    is_admin = bool(user.get("isPartnerAdmin"))
    is_employee = bool(user.get("isPartnerEmployee"))
    roles = []
    if is_admin:
        roles.append(ROLE_ADMIN)
    if is_employee:
        roles.append(ROLE_EMPLOYEE)
    return {
        "id": user.get("id"),
        "name": user.get("nickname") or user.get("name"),
        "supplierId": user.get("partnerId") or user.get("supplierId"),
        "roles": roles,
    }


def current_identity(token: str | None = None) -> dict[str, Any]:
    return identity_from_payload(api_request("/api/admin/user/current", token=token))


def require_role(*allowed: str) -> dict[str, Any]:
    identity = current_identity()
    if not set(identity["roles"]).intersection(allowed):
        raise VendorError("当前账号不是此命令允许的供应商角色。")
    return identity


def require_yes(args: argparse.Namespace, message: str) -> bool:
    if args.yes:
        return True
    print_payload(
        {"command": args.command, "status": "blocked_requires_yes", "message": message},
        args.compact,
    )
    return False


def parse_json_object(value: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise VendorError(f"{label} 不是合法 JSON。") from exc
    if not isinstance(payload, dict):
        raise VendorError(f"{label} 必须是 JSON object。")
    return payload


def command_config_set_server(args: argparse.Namespace) -> int:
    url = normalize_server_url(args.url)
    save_private(SERVER_FILE, url)
    print_payload({"command": "config set-server", "status": "ok", "serverConfigured": True}, args.compact)
    return 0


def command_config_show(args: argparse.Namespace) -> int:
    server, source = configured_server()
    print_payload(
        {"command": "config show", "status": "ok" if server else "missing", "serverConfigured": bool(server), "source": source},
        args.compact,
    )
    return 0 if server else 1


def command_auth_login(args: argparse.Namespace) -> int:
    if not sys.stdin.isatty():
        raise VendorError("登录必须在交互终端执行，以防 Token 进入命令历史或进程参数。")
    token = getpass.getpass("AccessToken（输入不显示）: ").strip()
    if not token:
        raise VendorError("AccessToken 不能为空。")
    identity = current_identity(token)
    if not identity["roles"]:
        raise VendorError("该 Token 不属于供应商管理员或供应商员工，未保存。")
    save_private(TOKEN_FILE, token)
    print_payload(
        {"command": "auth login", "status": "ok", "tokenPresent": True, "identity": identity},
        args.compact,
    )
    return 0


def command_auth_status(args: argparse.Namespace) -> int:
    token, source = configured_token()
    if not token:
        print_payload({"command": "auth status", "status": "missing", "tokenPresent": False}, args.compact)
        return 1
    identity = current_identity(token)
    print_payload(
        {"command": "auth status", "status": "ok", "tokenPresent": True, "source": source, "identity": identity},
        args.compact,
    )
    return 0


def command_auth_logout(args: argparse.Namespace) -> int:
    deleted = False
    try:
        TOKEN_FILE.unlink()
        deleted = True
    except FileNotFoundError:
        pass
    print_payload({"command": "auth logout", "status": "ok", "deleted": deleted}, args.compact)
    return 0


def command_whoami(args: argparse.Namespace) -> int:
    identity = require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    print_payload({"command": "whoami", "status": "ok", "identity": identity}, args.compact)
    return 0


def command_employee_list(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    body = {"page": args.page, "limit": args.limit, "id": args.id, "name": args.name, "phone": args.phone, "level": args.level}
    data = unwrap(api_request("/api/admin/partner-employee/list", method="POST", body=body, body_format="form"))
    print_payload({"command": args.command, "status": "ok", "data": data}, args.compact)
    return 0


def command_employee_detail(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    data = unwrap(api_request(f"/api/admin/partner-employee/{args.id}"))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_employee_mutate(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    if not require_yes(args, "这是供应商员工写操作，请确认后加 --yes。"):
        return 2
    if args.command == "partner-employee-create":
        path, body, fmt = "/api/admin/partner-employee/create", parse_json_object(args.content, "员工字段"), "json"
    elif args.command == "partner-employee-update":
        path, body, fmt = "/api/admin/partner-employee/update", {"id": args.id, **parse_json_object(args.content, "员工字段")}, "json"
    elif args.command == "partner-employee-switch":
        path, body, fmt = "/api/admin/partner-employee/switch_enabled", {"id": args.id, "enabled": args.enabled}, "form"
    else:
        path, body, fmt = "/api/admin/partner-employee/set_tag", {"id": args.id, "tag": args.tag}, "form"
    data = unwrap(api_request(path, method="POST", body=body, body_format=fmt))
    print_payload({"command": args.command, "status": "ok", "id": getattr(args, "id", None), "data": data}, args.compact)
    return 0


def command_order_list(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    body = {"page": args.page, "limit": args.limit, "projectName": args.project_name, "status": args.status, "deliveryStatus": args.delivery_status}
    data = unwrap(api_request("/api/admin/requirement-order/list", method="POST", body=body))
    print_payload({"command": args.command, "status": "ok", "data": data}, args.compact)
    return 0


def command_order_detail(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    data = unwrap(api_request(f"/api/admin/requirement-order/detail?id={args.id}"))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_order_action(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    if not require_yes(args, "这是需求订单写操作，请确认后加 --yes。"):
        return 2
    if args.command == "requirement-order-approve":
        path, body, fmt = "/api/admin/requirement-order/approve", {"id": args.id}, "json"
    else:
        if not args.reason.strip():
            raise VendorError("拒绝订单必须提供 --reason。")
        path, body, fmt = "/api/admin/requirement-order/reject", {"id": args.id, "reason": args.reason}, "form"
    data = unwrap(api_request(path, method="POST", body=body, body_format=fmt))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_purchase_list(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    params = {key: value for key, value in {"projectId": args.project_id, "productType": args.product_type}.items() if value not in (None, "")}
    query = f"?{urllib_parse.urlencode(params)}" if params else ""
    data = unwrap(api_request(f"/api/admin/purchase-order/partner_orders{query}"))
    print_payload({"command": args.command, "status": "ok", "data": data}, args.compact)
    return 0


def command_purchase_detail(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    data = unwrap(api_request(f"/api/admin/purchase-order/partner_order_detail?id={args.id}"))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_purchase_response_info(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    data = unwrap(api_request(f"/api/admin/purchase-order/respond_info?orderId={args.id}"))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_purchase_respond(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN)
    if not require_yes(args, "这是采购单响应写操作，请核对金额、税率和人员后加 --yes。"):
        return 2
    if args.purchase_amount <= 0 or not 0 <= args.tax_rate <= 1 or not args.user_ids:
        raise VendorError("采购金额必须大于 0，税率须在 0 到 1 之间，并至少指定一名员工。")
    body = {"orderId": args.id, "purchaseAmount": args.purchase_amount, "taxRate": args.tax_rate, "userIds": args.user_ids}
    if args.work_hour_error_reason:
        body["workHourErrorReason"] = args.work_hour_error_reason
    if args.work_hour_error_reason_detail:
        body["workHourErrorReasonDetail"] = args.work_hour_error_reason_detail
    data = unwrap(api_request("/api/admin/purchase-order/partner_respond", method="POST", body=body))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_work_hours_list(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    body: dict[str, Any] = {"page": args.page, "limit": args.limit}
    for attr, key in (
        ("requirement_order_id", "requirementOrderId"),
        ("order_serial_no", "orderSerialNo"),
        ("requirement_id", "requirementId"),
        ("project_name", "projectName"),
        ("user_id", "userId"),
        ("employee_name", "employeeName"),
        ("day_begin", "dayBegin"),
        ("day_end", "dayEnd"),
        ("status", "status"),
    ):
        value = getattr(args, attr, None)
        if value not in (None, ""):
            body[key] = value
    data = unwrap(api_request("/api/admin/security-product/work-record/list", method="POST", body=body))
    print_payload({"command": args.command, "status": "ok", "filters": body, "data": data}, args.compact)
    return 0


def command_work_hours_detail(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    data = unwrap(api_request(f"/api/admin/security-product/work-record/detail?id={args.id}"))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_work_hours_submit(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    if not require_yes(args, "这是工时提交写操作，请核对订单、工程师、日期和工时后加 --yes。"):
        return 2
    if not args.requirement_order_id and not args.order_serial_no:
        raise VendorError("请提供 --requirement-order-id 或 --order-serial-no。")
    if args.work_hours <= 0 or not float(args.work_hours).is_integer():
        raise VendorError("工时必须是正整数小时。")
    body = {
        "requirementOrderId": args.requirement_order_id,
        "orderSerialNo": args.order_serial_no,
        "userId": args.user_id,
        "date": args.date,
        "workHours": int(args.work_hours),
        "remark": args.remark,
    }
    data = unwrap(api_request("/api/admin/security-product/work-record/submit", method="POST", body=body))
    print_payload({"command": args.command, "status": "ok", "data": data}, args.compact)
    return 0


def command_work_hours_update(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    if not require_yes(args, "这是工时修改写操作，请核对修改内容和原因后加 --yes。"):
        return 2
    if args.work_hours <= 0 or not float(args.work_hours).is_integer():
        raise VendorError("工时必须是正整数小时。")
    if not args.reason.strip():
        raise VendorError("修改工时必须提供 --reason。")
    body = {"id": args.id, "date": args.date, "workHours": int(args.work_hours), "remark": args.remark, "reason": args.reason}
    data = unwrap(api_request("/api/admin/security-product/work-record/update", method="POST", body=body))
    print_payload({"command": args.command, "status": "ok", "id": args.id, "data": data}, args.compact)
    return 0


def command_work_hours_check(args: argparse.Namespace) -> int:
    if args.purchase_order_id:
        require_role(ROLE_ADMIN)
        data = unwrap(api_request(f"/api/admin/purchase-order/partner_order_detail?id={args.purchase_order_id}"))
        check = data.get("workHourCheck") if isinstance(data, dict) else None
        scope = {"purchaseOrderId": args.purchase_order_id}
    else:
        require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
        data = unwrap(api_request(f"/api/admin/requirement-order/detail?id={args.requirement_order_id}"))
        if not isinstance(data, dict):
            raise VendorError("订单工时响应无法解析。")
        check = {key: data.get(key) for key in (
            "deliveryMaterialCount", "deliveryMaterialUploaded", "workRecordCount",
            "workRecordCompleted", "workRecordApproved", "orderDeliveryStatus",
            "orderDeliveryStatusCode", "orderCloseTime", "workHourSummaries",
        )}
        scope = {"requirementOrderId": args.requirement_order_id}
    print_payload({"command": args.command, "status": "ok", "scope": scope, "data": check or {}}, args.compact)
    return 0


def command_process_trace(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    scope = {
        "requirementId": args.requirement_id,
        "requirementOrderId": args.requirement_order_id,
        "purchaseOrderId": args.purchase_order_id,
    }
    if not any(scope.values()):
        raise VendorError("请至少提供 --requirement-id、--requirement-order-id 或 --purchase-order-id。")
    params = {key: value for key, value in scope.items() if value}
    if args.event_type:
        params["eventType"] = args.event_type
    params.update({"page": args.page, "limit": args.limit})
    data = unwrap(api_request(f"/api/admin/security-product/process-event/list?{urllib_parse.urlencode(params)}"))
    print_payload({"command": args.command, "status": "ok", "filters": params, "data": data}, args.compact)
    return 0


def command_materials_by_order(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    data = unwrap(api_request(f"/api/admin/requirement-order-project-document/list?requirementOrderId={args.requirement_order_id}"))
    print_payload({"command": args.command, "status": "ok", "requirementOrderId": args.requirement_order_id, "data": data}, args.compact)
    return 0


def command_material_download(args: argparse.Namespace) -> int:
    require_role(ROLE_ADMIN, ROLE_EMPLOYEE)
    target = Path(args.output).expanduser().resolve()
    if target.exists() and not args.force:
        raise VendorError(f"输出文件已存在：{target}。确认覆盖后加 --force。")
    target.parent.mkdir(parents=True, exist_ok=True)
    server, _ = configured_server()
    token, _ = configured_token()
    request = urllib_request.Request(
        f"{server}/api/admin/requirement-order-project-document/download?id={args.id}",
        headers={"Authorization": auth_header(token), "Accept": "application/octet-stream,*/*"},
    )
    temporary = target.with_name(f".{target.name}.part")
    try:
        with urllib_request.urlopen(request, timeout=60, context=ssl_context()) as response:
            content_type = response.headers.get("Content-Type", "")
            content = response.read()
        if "json" in content_type.lower():
            raise VendorError("材料下载被服务端拒绝。")
        temporary.write_bytes(content)
        temporary.replace(target)
    except urllib_error.HTTPError as exc:
        raise VendorError(f"材料下载失败（HTTP {exc.code}）。") from exc
    except urllib_error.URLError as exc:
        raise VendorError(f"材料下载连接失败：{exc.reason}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    print_payload({"command": args.command, "status": "ok", "id": args.id, "output": str(target), "bytes": target.stat().st_size}, args.compact)
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--compact", action="store_true", help="输出紧凑 JSON，适合脚本和 Agent 解析")


def add_write(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes", action="store_true", help="确认执行写操作")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="云集供应商命令行工具")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=ChineseArgumentParser)

    config = sub.add_parser("config", help="配置供应商服务地址")
    config_sub = config.add_subparsers(dest="config_command", required=True, parser_class=ChineseArgumentParser)
    set_server = config_sub.add_parser("set-server", help="保存服务地址")
    add_common(set_server)
    set_server.add_argument("--url", required=True, help="由服务方提供的 HTTPS 地址")
    set_server.set_defaults(func=command_config_set_server)
    show = config_sub.add_parser("show", help="查看服务地址配置状态")
    add_common(show)
    show.set_defaults(func=command_config_show)

    auth = sub.add_parser("auth", help="认证管理")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True, parser_class=ChineseArgumentParser)
    for name, help_text, func in (
        ("login", "无回显交互登录", command_auth_login),
        ("status", "检查登录状态", command_auth_status),
        ("logout", "删除本机 Token", command_auth_logout),
    ):
        item = auth_sub.add_parser(name, help=help_text)
        add_common(item)
        item.set_defaults(func=func)

    whoami = sub.add_parser("whoami", help="查看供应商身份摘要")
    add_common(whoami)
    whoami.set_defaults(func=command_whoami)

    employee_list = sub.add_parser("partner-employee-list", help="[供应商管理员] 查询员工")
    add_common(employee_list)
    employee_list.add_argument("--page", type=int, default=1)
    employee_list.add_argument("--limit", type=int, default=20)
    employee_list.add_argument("--id", type=int)
    employee_list.add_argument("--name", default="")
    employee_list.add_argument("--phone", default="")
    employee_list.add_argument("--level", default="")
    employee_list.set_defaults(func=command_employee_list)

    employee_detail = sub.add_parser("partner-employee-detail", help="[供应商管理员] 查询员工详情")
    add_common(employee_detail)
    employee_detail.add_argument("--id", type=int, required=True)
    employee_detail.set_defaults(func=command_employee_detail)

    employee_create = sub.add_parser("partner-employee-create", help="[供应商管理员] 创建员工")
    add_common(employee_create); add_write(employee_create)
    employee_create.add_argument("--content", required=True, help="员工字段 JSON")
    employee_create.set_defaults(func=command_employee_mutate)

    employee_update = sub.add_parser("partner-employee-update", help="[供应商管理员] 更新员工")
    add_common(employee_update); add_write(employee_update)
    employee_update.add_argument("--id", type=int, required=True)
    employee_update.add_argument("--content", required=True, help="员工字段 JSON")
    employee_update.set_defaults(func=command_employee_mutate)

    employee_switch = sub.add_parser("partner-employee-switch", help="[供应商管理员] 启用或停用员工")
    add_common(employee_switch); add_write(employee_switch)
    employee_switch.add_argument("--id", type=int, required=True)
    employee_switch.add_argument("--enabled", action="store_true", help="启用；不传表示停用")
    employee_switch.set_defaults(func=command_employee_mutate)

    employee_tag = sub.add_parser("partner-employee-tag", help="[供应商管理员] 设置员工标签")
    add_common(employee_tag); add_write(employee_tag)
    employee_tag.add_argument("--id", type=int, required=True)
    employee_tag.add_argument("--tag", required=True)
    employee_tag.set_defaults(func=command_employee_mutate)

    order_list = sub.add_parser("requirement-order-list", help="[供应商管理员] 查询需求订单")
    add_common(order_list)
    order_list.add_argument("--page", type=int, default=1)
    order_list.add_argument("--limit", type=int, default=20)
    order_list.add_argument("--project-name", default="")
    order_list.add_argument("--status", type=int)
    order_list.add_argument("--delivery-status", type=int)
    order_list.set_defaults(func=command_order_list)

    order_detail = sub.add_parser("requirement-order-detail", help="[供应商管理员] 查询需求订单详情")
    add_common(order_detail)
    order_detail.add_argument("--id", type=int, required=True)
    order_detail.set_defaults(func=command_order_detail)

    for name, label in (("requirement-order-approve", "接单"), ("requirement-order-reject", "拒单")):
        action = sub.add_parser(name, help=f"[供应商管理员] {label}")
        add_common(action); add_write(action)
        action.add_argument("--id", type=int, required=True)
        if name.endswith("reject"):
            action.add_argument("--reason", required=True)
        action.set_defaults(func=command_order_action)

    purchase_list = sub.add_parser("partner-purchase-list", help="[供应商管理员] 查询采购单")
    add_common(purchase_list)
    purchase_list.add_argument("--project-id", type=int)
    purchase_list.add_argument("--product-type", default="")
    purchase_list.set_defaults(func=command_purchase_list)

    for name, label, func in (
        ("partner-purchase-detail", "查询采购单详情", command_purchase_detail),
        ("partner-purchase-response-info", "查询采购单响应信息", command_purchase_response_info),
    ):
        item = sub.add_parser(name, help=f"[供应商管理员] {label}")
        add_common(item)
        item.add_argument("--id", type=int, required=True)
        item.set_defaults(func=func)

    respond = sub.add_parser("partner-purchase-respond", help="[供应商管理员] 响应采购单")
    add_common(respond); add_write(respond)
    respond.add_argument("--id", type=int, required=True)
    respond.add_argument("--purchase-amount", type=float, required=True)
    respond.add_argument("--tax-rate", type=float, required=True)
    respond.add_argument("--user-ids", type=int, nargs="+", required=True)
    respond.add_argument("--work-hour-error-reason", default="", help="按接口返回选项填写工时误差原因")
    respond.add_argument("--work-hour-error-reason-detail", default="", help="工时误差原因补充说明")
    respond.set_defaults(func=command_purchase_respond)

    work_list = sub.add_parser("work-hours-list", help="[供应商管理员/员工] 查询安全产品工时")
    add_common(work_list)
    work_list.add_argument("--page", type=int, default=1)
    work_list.add_argument("--limit", type=int, default=20)
    work_list.add_argument("--requirement-order-id", type=int)
    work_list.add_argument("--order-serial-no", default="")
    work_list.add_argument("--requirement-id", type=int)
    work_list.add_argument("--project-name", default="")
    work_list.add_argument("--user-id", type=int)
    work_list.add_argument("--employee-name", default="")
    work_list.add_argument("--day-begin", default="", help="YYYY-MM-DD")
    work_list.add_argument("--day-end", default="", help="YYYY-MM-DD")
    work_list.add_argument("--status", type=int, choices=[0, 2, 3])
    work_list.set_defaults(func=command_work_hours_list)

    work_detail = sub.add_parser("work-hours-detail", help="[供应商管理员/员工] 查询工时详情及编辑历史")
    add_common(work_detail)
    work_detail.add_argument("--id", type=int, required=True)
    work_detail.set_defaults(func=command_work_hours_detail)

    work_submit = sub.add_parser("work-hours-submit", help="[供应商管理员/员工] 提交安全产品工时")
    add_common(work_submit); add_write(work_submit)
    work_submit.add_argument("--requirement-order-id", type=int)
    work_submit.add_argument("--order-serial-no", default="")
    work_submit.add_argument("--user-id", type=int, required=True, help="实际填报工程师用户 ID")
    work_submit.add_argument("--date", required=True, help="YYYY-MM-DD")
    work_submit.add_argument("--work-hours", type=float, required=True, help="正整数小时")
    work_submit.add_argument("--remark", default="")
    work_submit.set_defaults(func=command_work_hours_submit)

    work_update = sub.add_parser("work-hours-update", help="[供应商管理员/员工] 修改安全产品工时")
    add_common(work_update); add_write(work_update)
    work_update.add_argument("--id", type=int, required=True)
    work_update.add_argument("--date", required=True, help="YYYY-MM-DD")
    work_update.add_argument("--work-hours", type=float, required=True, help="正整数小时")
    work_update.add_argument("--remark", default="")
    work_update.add_argument("--reason", required=True)
    work_update.set_defaults(func=command_work_hours_update)

    work_check = sub.add_parser("work-hours-check", help="[供应商管理员/员工] 查看订单或采购单工时核对")
    add_common(work_check)
    work_scope = work_check.add_mutually_exclusive_group(required=True)
    work_scope.add_argument("--requirement-order-id", type=int)
    work_scope.add_argument("--purchase-order-id", type=int)
    work_check.set_defaults(func=command_work_hours_check)

    process_trace = sub.add_parser("process-trace", help="[供应商管理员/员工] 查询本人授权范围内的流程事件")
    add_common(process_trace)
    process_trace.add_argument("--requirement-id", type=int)
    process_trace.add_argument("--requirement-order-id", type=int)
    process_trace.add_argument("--purchase-order-id", type=int)
    process_trace.add_argument("--event-type", default="")
    process_trace.add_argument("--page", type=int, default=1)
    process_trace.add_argument("--limit", type=int, choices=range(1, 101), default=100)
    process_trace.set_defaults(func=command_process_trace)

    materials = sub.add_parser("materials-by-order", help="[供应商管理员/员工] 查询订单交付材料")
    add_common(materials)
    materials.add_argument("--requirement-order-id", type=int, required=True)
    materials.set_defaults(func=command_materials_by_order)

    download = sub.add_parser("material-download", help="[供应商管理员/员工] 直接下载交付材料")
    add_common(download)
    download.add_argument("--id", type=int, required=True)
    download.add_argument("--output", required=True)
    download.add_argument("--force", action="store_true")
    download.set_defaults(func=command_material_download)
    return parser


def main() -> int:
    configure_output()
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print_payload({"command": getattr(args, "command", ""), "status": "error", "message": "用户中断。"}, getattr(args, "compact", False))
        return 130
    except VendorError as exc:
        print_payload({"command": getattr(args, "command", ""), "status": "error", "message": str(exc)}, getattr(args, "compact", False))
        return 1
    except json.JSONDecodeError:
        print_payload({"command": getattr(args, "command", ""), "status": "error", "message": "输入不是合法 JSON。"}, getattr(args, "compact", False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
