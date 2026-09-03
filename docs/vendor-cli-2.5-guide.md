# 云集供应商 CLI 2.5 使用手册

> 适用对象：云集供应商负责人及经授权的供应商工程师

### 1. 本次更新

供应商 CLI 2.5 新增安全产品工时能力：

- 工程师按需求订单填写和修改本人实际工时；
- 供应商负责人查询本供应商工时，并可代名下工程师填写或修改；
- 供应商负责人响应采购单前核对工时、交付物和采购响应人天；
- 双方可查看本人授权订单的流程事件。

### 2. 角色动作总览

| 角色 | 需要完成的动作 | 操作前确认 |
| --- | --- | --- |
| 工程师 | 每日填写实际工作日期和工时；发现错误时及时修改 | 订单已绑定本人，日期在服务期内，工时与实际一致 |
| 供应商负责人 | 检查工程师工时；必要时代填或修改；响应采购单并确认金额、人员、交付物和工时 | 工程师归属正确，工时无缺失或重复，误差原因已说明 |

### 3. 安装与登录

解压服务方提供的安装包后执行：

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
yunji auth login
yunji auth status --compact
yunji whoami --compact
```

正式供应商 CLI 固定连接云集正式环境，不需要也不允许切换服务地址。AccessToken 输入过程不会显示。每位用户必须使用自己的 Token，不得通过聊天、邮件、脚本或共享文档传递。

### 4. 工程师操作

查询本人订单工时：

```bash
yunji work-hours-list --requirement-order-id <需求订单ID> --compact
```

填写工时：

```bash
yunji work-hours-submit \
  --requirement-order-id <需求订单ID> \
  --user-id <本人用户ID> \
  --date 2026-09-03 \
  --work-hours 8 \
  --remark '<实际工作内容>' \
  --yes \
  --compact
```

修改工时：

```bash
yunji work-hours-update \
  --id <工时记录ID> \
  --date 2026-09-03 \
  --work-hours 4 \
  --reason '<修改原因>' \
  --yes \
  --compact
```

填写要求：

- `--work-hours` 必须为正整数小时；
- 日期不能晚于当天，且必须在订单服务时间内；
- 同一订单、工程师和日期不能重复填写；
- `--user-id` 表示实际工作的工程师，不是操作人。

### 5. 供应商负责人操作

查询本供应商工程师工时：

```bash
yunji work-hours-list \
  --employee-name '<工程师姓名>' \
  --day-begin 2026-09-01 \
  --day-end 2026-09-30 \
  --compact
```

负责人代填时，仍在 `--user-id` 中填写实际工程师。系统会保留负责人为实际操作人，并在工时详情的 `editHistory` 中记录修改历史。

响应采购单前先核对：

```bash
yunji partner-purchase-response-info --id <采购单ID> --compact
yunji work-hours-check --purchase-order-id <采购单ID> --compact
```

重点查看：

- `workHourCheckStatus`：总体核对状态；
- `workHourCheckIssues`：缺失、重复、超期、超预估或人天不一致；
- `workHourCheckItems`：每名工程师的工时明细；
- `deliveryMaterialUploaded`：交付物是否上传；
- `workHourErrorReasonRequired`：是否必须填写误差原因。

需要填写误差原因时：

```bash
yunji partner-purchase-respond \
  --id <采购单ID> \
  --purchase-amount <采购金额> \
  --tax-rate <税率> \
  --user-ids <工程师用户ID> \
  --work-hour-error-reason '<接口返回的原因选项>' \
  --work-hour-error-reason-detail '<补充说明>' \
  --yes \
  --compact
```

误差原因必须从接口返回的 `workHourErrorReasonOptions` 中选择。

### 6. 流程查询

```bash
yunji process-trace --requirement-order-id <需求订单ID> --compact
```

流程事件仅返回当前账号有权访问的数据。`historyComplete=false` 或旧订单返回空事件时，表示历史链路无法完整还原，不应使用更新时间推测业务节点时间。

### 7. 安全边界

- 所有提交、修改、接单、拒单和采购单响应都要求 `--yes`；
- 供应商工程师不能查看或响应采购单；
- 不得修改 ID 尝试访问其他供应商或其他工程师数据；
- 遇到 `401`、`403` 或 `404` 应停止操作并联系项目联系人；
- 工具不提供任意 API 调用、内部审批或平台管理命令。
