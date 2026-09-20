# yunji-cli-vendor

`yunji-cli-vendor` 是面向云集供应商管理员和供应商员工的命令行工具。它只包含供应商业务所需能力，所有可见数据和写操作均由服务端根据个人 AccessToken、供应商归属、角色和订单归属再次校验。

## 安装

环境要求：Windows 10 或以上、macOS 或 Linux，Python 3.10 或以上。

从服务方提供的正式安装包解压后，按操作系统执行。安装器只写入当前用户目录，不需要管理员权限。

Windows：

```powershell
.\install.cmd
```

macOS / Linux：

```bash
./install.sh
```

默认安装到当前用户目录，不需要管理员权限：

Windows：

```text
%LOCALAPPDATA%\yunji-cli-vendor
%LOCALAPPDATA%\Programs\yunji-cli-vendor\bin
```

macOS 或 Linux：

```text
~/.local/share/yunji-cli-vendor
~/.local/bin/yunji
```

Windows 安装器会将命令目录加入当前用户 PATH。安装完成后关闭并重新打开 PowerShell。

若 macOS / Linux 终端提示 `yunji: command not found`，先将命令目录加入 PATH：

Zsh：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Bash：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 登录

正式供应商 CLI 固定连接云集正式环境，不需要也不允许切换服务地址。服务方会单独提供个人 AccessToken，在交互终端登录：

```bash
yunji auth login
yunji auth status --compact
yunji whoami --compact
```

`auth login` 输入过程不会显示 Token。工具不支持通过命令行参数或管道传入 Token，避免 Token 进入 Shell 历史、进程列表或 Agent 日志。

Token 保存在当前用户目录：Windows 为 `%USERPROFILE%\.config\yunji-cli-vendor\access-token`，macOS/Linux 为 `~/.config/yunji-cli-vendor/access-token`。macOS/Linux 文件权限为 `600`；Windows 依赖当前用户目录的 NTFS 访问控制。每位用户必须使用自己的 Token，不得共享。

## 角色能力

| 角色 | 能力 |
|---|---|
| 供应商管理员 | 查询、创建和维护本供应商员工；查询本供应商需求订单；接单、拒单或更换安全产品订单工程师；查询和响应本供应商采购单；代员工填写或修改工时；查询工时核对结果和流程事件；查询、上传、删除和下载授权订单的交付材料 |
| 供应商员工 | 查询、填写和修改本人工时记录；查询、上传、删除和下载本人有权访问订单的交付材料 |

同一安装包适用于两类角色。CLI 会先检查当前供应商身份，服务端再执行最终权限校验。供应商员工不使用 `work-hours-check` 和 `process-trace`；供应商员工只能操作本人被绑定的安全产品订单材料，且只能删除本人上传的材料。

## 常用命令

供应商管理员：

```bash
yunji requirement-order-list --limit 20 --compact
yunji requirement-order-detail --id <需求订单ID> --compact
yunji requirement-order-approve --id <需求订单ID> --yes --compact
yunji requirement-order-approve-product --id <安全产品需求订单ID> --yes --compact
yunji requirement-order-reject --id <需求订单ID> --reason '<拒绝原因>' --yes --compact

yunji requirement-order-update-engineers \
  --id <安全产品需求订单ID> \
  --user-ids <保留的工程师用户ID> <新增工程师用户ID> \
  --yes \
  --compact

yunji partner-purchase-list --compact
yunji partner-purchase-detail --id <采购单ID> --compact
yunji partner-purchase-response-info --id <采购单ID> --compact
yunji partner-purchase-respond \
  --id <采购单ID> \
  --purchase-amount <采购金额> \
  --tax-rate <0到1之间的税率> \
  --user-ids <员工ID> \
  --work-hour-error-reason '<接口返回的误差原因>' \
  --work-hour-error-reason-detail '<补充说明>' \
  --yes \
  --compact
```

响应采购单前先执行：

```bash
yunji partner-purchase-response-info --id <采购单ID> --compact
yunji work-hours-check --purchase-order-id <采购单ID> --compact
```

若返回 `workHourErrorReasonRequired=true`，必须从 `workHourErrorReasonOptions` 中选择原因。

安全产品工时：

```bash
yunji work-hours-list --requirement-order-id <需求订单ID> --compact
yunji work-hours-detail --id <工时记录ID> --compact

yunji work-hours-submit \
  --requirement-order-id <需求订单ID> \
  --user-id <工程师用户ID> \
  --date 2026-09-03 \
  --work-hours 8 \
  --remark '<工作说明>' \
  --yes \
  --compact

yunji work-hours-update \
  --id <工时记录ID> \
  --date 2026-09-03 \
  --work-hours 4 \
  --reason '<修改原因>' \
  --yes \
  --compact

yunji process-trace --requirement-order-id <需求订单ID> --compact
```

`--user-id` 始终表示实际填报工程师。供应商管理员代填时，后端会记录管理员为实际操作人。流程事件只返回当前账号有权访问的订单数据；`historyComplete=false` 表示旧数据事件链不完整。

员工管理：

```bash
yunji partner-employee-list --compact
yunji partner-employee-detail --id <员工记录ID> --compact
yunji partner-employee-create --content '{"name":"示例姓名"}' --yes --compact
yunji partner-employee-update --id <员工记录ID> --content '{"name":"示例姓名"}' --yes --compact
yunji partner-employee-switch --id <员工记录ID> --enabled --yes --compact
yunji partner-employee-tag --id <员工记录ID> --tag '<标签>' --yes --compact
```

交付材料：

```bash
yunji materials-by-order --requirement-order-id <需求订单ID> --compact
yunji material-download --id <材料ID> --output ./delivery-material.docx --compact
yunji material-upload --requirement-order-id <需求订单ID> --file ./delivery-material.docx --yes --compact
yunji material-delete --id <材料ID> --yes --compact
```

`material-upload` 支持重复传入 `--file`。上传前会检查 100M 上限和扩展名白名单；上传后不会输出对象存储地址。`requirement-order-update-engineers` 是全量替换：`--user-ids` 必须包含所有需要保留的原成员，否则原成员会被解绑。工具不提供独立下载凭证命令，下载凭证不会输出到终端。

## 写操作与 Agent

创建、修改、接单、拒单、更换订单工程师、上传或删除交付材料、工时提交与修改和采购单响应等写操作均要求 `--yes`。推荐流程：

1. `yunji whoami --compact` 确认当前供应商身份。
2. 查询目标对象及最新状态。
3. 使用 `yunji <命令> --help` 核对参数。
4. 向用户展示对象、动作和影响。
5. 用户明确确认后才添加 `--yes`。
6. 操作完成后重新查询确认结果。

Agent 不得编造 ID，不得更换其他对象试探权限。遇到 `401`、`403` 或 `404` 应立即停止并联系服务方。

## 卸载与退出

退出并删除本机 Token：

```bash
yunji auth logout
```

卸载前先执行 `command -v yunji` 确认安装路径。不要在未确认路径时递归删除目录。

## 反馈

反馈时请提供命令名称、用户角色、发生时间和脱敏后的错误信息。不要发送 AccessToken、密码、完整交付材料或下载链接。
