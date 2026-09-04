# 云集供应商 CLI 使用手册（供应商版）

> 适用对象：云集供应商负责人和经授权的供应商工程师
> 版本定位：包含供应商基础业务命令，以及 2.5 新增的安全产品工时和流程事件能力

### 1. 能力总览

| 能力 | 供应商负责人 | 供应商工程师 |
| --- | --- | --- |
| 登录、身份确认、退出 | 支持 | 支持 |
| 员工查询和维护 | 支持 | 不支持 |
| 需求订单查询、接单、拒单 | 支持 | 不支持 |
| 采购单查询和响应 | 支持 | 不支持 |
| 安全产品工时查询、填写、修改 | 支持本供应商工程师 | 支持本人工时 |
| 工时核对结果查询 | 支持采购单和订单 | 支持本人订单 |
| 流程事件查询 | 授权范围内 | 授权范围内 |
| 订单交付材料查询和下载 | 授权范围内 | 授权范围内 |

同一安装包适用于两类角色。客户端角色检查只用于减少误操作，最终权限和数据范围由云集服务端校验。

### 2. 安装、登录与环境

供应商 CLI 支持 Windows 10 或以上、macOS 和 Linux，要求 Python 3.10 或以上。解压服务方提供的安装包后，按当前系统执行安装命令；安装器只写入当前用户目录，不需要管理员权限。

Windows：

```powershell
.\install.cmd
```

安装完成后关闭并重新打开 PowerShell。安装器会把 `yunji` 命令目录加入当前用户 PATH。

macOS / Linux：

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
```

上面的 `export` 让当前终端立即识别 `yunji`。如需长期生效，把该行加入 `~/.zshrc` 或 `~/.bashrc`。

### 3. 首次登录与环境

安装完成后，Windows、macOS 和 Linux 继续执行相同命令：

```bash
yunji auth login
yunji auth status --compact
yunji whoami --compact
```

正式供应商 CLI 固定连接云集正式环境，不需要配置服务地址，也不允许切换到其他地址。`config show` 可用于检查兼容配置；如历史配置不是正式地址，CLI 会在发送请求前停止。

`auth login` 必须在交互终端执行，Token 输入过程不回显。Token 保存在当前用户目录；Windows 使用 `%USERPROFILE%\.config\yunji-cli-vendor\access-token`，macOS/Linux 使用 `~/.config/yunji-cli-vendor/access-token`。每位用户必须使用自己的 AccessToken；不要通过聊天、邮件、工单、命令参数、脚本或共享文档传递 Token。

所有命令支持 `--compact`，输出紧凑 JSON，便于脚本和 AI Agent 解析。所有写操作必须显式添加 `--yes`。

### 4. 通用命令

| 命令 | 角色 | 用途 |
| --- | --- | --- |
| `yunji auth login` | 全部 | 交互式保存个人 AccessToken |
| `yunji auth status` | 全部 | 检查本机 Token 和当前身份 |
| `yunji auth logout` | 全部 | 删除本机 Token |
| `yunji whoami` | 全部 | 查看供应商身份摘要 |
| `yunji config show` | 全部 | 查看服务地址配置来源和状态 |

开始工作前建议执行：

```bash
yunji auth status --compact
yunji whoami --compact
```

### 5. 员工管理

供应商负责人可以查询和维护本供应商员工。

```bash
yunji partner-employee-list --page 1 --limit 20 --compact
yunji partner-employee-detail --id <员工记录ID> --compact
```

创建和更新使用接口要求的员工字段 JSON：

```bash
yunji partner-employee-create \
  --content '<员工字段JSON>' \
  --yes --compact

yunji partner-employee-update \
  --id <员工记录ID> \
  --content '<需要更新的员工字段JSON>' \
  --yes --compact
```

启用、停用和设置标签：

```bash
yunji partner-employee-switch --id <员工记录ID> --enabled --yes --compact
yunji partner-employee-switch --id <员工记录ID> --yes --compact
yunji partner-employee-tag --id <员工记录ID> --tag '<标签>' --yes --compact
```

执行修改前先用列表确认员工记录 ID；该 ID 不一定等于云集用户 ID。

### 6. 需求订单

供应商负责人可以查询本供应商需求订单并接单或拒单。

```bash
yunji requirement-order-list \
  --page 1 \
  --limit 20 \
  --compact
```

可用筛选包括 `--project-name`、`--status` 和 `--delivery-status`。查看完整详情：

```bash
yunji requirement-order-detail --id <需求订单ID> --compact
```

接单：

```bash
yunji requirement-order-approve \
  --id <需求订单ID> \
  --yes --compact
```

拒单：

```bash
yunji requirement-order-reject \
  --id <需求订单ID> \
  --reason '<拒绝原因>' \
  --yes --compact
```

### 7. 采购单

供应商负责人可以查询采购单、获取响应回填信息并提交采购单响应。

```bash
yunji partner-purchase-list \
  --project-id <项目ID> \
  --product-type '<产品类型>' \
  --compact

yunji partner-purchase-detail --id <采购单ID> --compact
yunji partner-purchase-response-info --id <采购单ID> --compact
```

响应前必须核对采购金额、税率、参与工程师、交付物和工时。2.5 后响应信息会返回工时核对结果。

常规响应：

```bash
yunji partner-purchase-respond \
  --id <采购单ID> \
  --purchase-amount <采购金额> \
  --tax-rate <税率> \
  --user-ids <工程师用户ID> \
  --yes --compact
```

需要填写工时误差原因时：

```bash
yunji partner-purchase-respond \
  --id <采购单ID> \
  --purchase-amount <采购金额> \
  --tax-rate <税率> \
  --user-ids <工程师用户ID> \
  --work-hour-error-reason '<接口返回的原因选项>' \
  --work-hour-error-reason-detail '<补充说明>' \
  --yes --compact
```

误差原因必须从 `workHourErrorReasonOptions` 中选择。多个工程师用户 ID 按命令帮助要求传递。

### 8. 工时填写

工程师填写本人工时；供应商负责人可代本供应商名下工程师填写。

```bash
yunji work-hours-list \
  --requirement-order-id <需求订单ID> \
  --compact

yunji work-hours-detail --id <工时记录ID> --compact
```

负责人可按工程师和日期查询：

```bash
yunji work-hours-list \
  --employee-name '<工程师姓名>' \
  --day-begin 2026-09-01 \
  --day-end 2026-09-30 \
  --compact
```

提交工时：

```bash
yunji work-hours-submit \
  --requirement-order-id <需求订单ID> \
  --user-id <实际工作工程师的用户ID> \
  --date 2026-09-03 \
  --work-hours 8 \
  --remark '<实际工作内容>' \
  --yes --compact
```

修改工时：

```bash
yunji work-hours-update \
  --id <工时记录ID> \
  --date 2026-09-03 \
  --work-hours 4 \
  --remark '<最新工作内容>' \
  --reason '<修改原因>' \
  --yes --compact
```

工时必须是正整数小时。日期不能晚于当天，必须落在订单服务时间内；同一订单、工程师和日期不能重复填写。`--user-id` 始终表示实际工作的工程师，不是登录操作人；代填操作人和修改历史由服务端记录。

### 9. 工时核对

按需求订单查询：

```bash
yunji work-hours-check \
  --requirement-order-id <需求订单ID> \
  --compact
```

按采购单查询：

```bash
yunji work-hours-check \
  --purchase-order-id <采购单ID> \
  --compact
```

重点检查：

- `workHourCheckStatus`：总体核对状态；
- `workHourCheckIssues`：缺失、重复、超期、超预估或不一致问题；
- `workHourCheckItems`：每名工程师明细；
- `deliveryMaterialUploaded`：交付物是否上传；
- `workHourErrorReasonRequired`：响应时是否必须填写误差原因。

不要只看提示文案；应同时读取状态字段和问题列表。

### 10. 流程事件

流程事件至少指定需求单、需求订单或采购单中的一个范围：

```bash
yunji process-trace --requirement-id <需求ID> --compact
yunji process-trace --requirement-order-id <需求订单ID> --compact
yunji process-trace --purchase-order-id <采购单ID> --compact
```

可用 `--event-type` 筛选事件类型，用 `--page` 和 `--limit` 控制分页，最大 `--limit` 为 100。

业务耗时使用 `eventTime` 计算。`historyComplete=false` 或旧订单返回空事件时，表示历史链路无法完整还原，不应使用对象更新时间反推业务节点时间。

### 11. 交付材料

查询订单交付材料：

```bash
yunji materials-by-order \
  --requirement-order-id <需求订单ID> \
  --compact
```

下载材料：

```bash
yunji material-download \
  --id <材料ID> \
  --output ./delivery-material.docx \
  --compact
```

目标文件已存在时不会覆盖；确认后才能添加 `--force`。材料可能包含项目敏感信息，应下载到受控目录，按公司和客户要求保存与销毁。

### 12. 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 提示未登录 | 在交互终端执行 `yunji auth login` |
| `401` | Token 无效或过期；重新登录后确认身份 |
| `403` | 当前角色或数据范围无权限；不要更换 ID 重试 |
| `404` | 对象不存在或不可见；先通过列表查询授权对象 |
| 提示缺少 `--yes` | 确认操作摘要后显式添加 `--yes` |
| 服务地址被拒绝 | 移除非正式环境覆盖，使用 CLI 内置正式地址 |

### 13. 安全边界

- 供应商工程师不能查询或响应采购单；
- 供应商负责人只能操作本供应商和名下工程师授权范围内的数据；
- 不得修改 ID 尝试访问其他供应商、其他工程师或其他订单；
- 客户端不提供任意 API 调用、内部审批或平台管理命令；
- 遇到权限、状态或归属不确定时停止操作并联系项目联系人。
