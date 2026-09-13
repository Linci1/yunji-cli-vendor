# 云集开放 API 使用指南（供应商版）

| 版本 | 维护日期 | 更新内容 |
| --- | --- | --- |
| 2.5.2 | 2026-09-13 | 明确供应商员工不需要订单级工时核对和流程事件；明确交付材料仅开放查询和下载。 |

> 适用对象：已接入云集平台的供应商应用和自动化工具
> 版本定位：包含供应商基础 API，以及 2.5 新增的安全产品工时和流程事件接口

### 1. 接入边界

每位用户使用自己的 AccessToken，服务端根据供应商归属、工程师绑定关系、角色、订单状态和数据范围校验每次请求。

推荐请求头：

```http
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
Accept: application/json
```

接入后先确认身份：

```http
GET /api/admin/user/current
```

客户端应保存当前用户 ID、供应商 ID 和角色摘要，不得假定请求参数可以扩大数据范围。

### 2. 能力地图

| 能力 | 接口路径 | 方法 | 说明 |
| --- | --- | --- | --- |
| 当前身份 | `/api/admin/user/current` | GET | 当前用户、供应商和角色 |
| 员工列表 | `/api/admin/partner-employee/list` | POST | 查询本供应商员工 |
| 员工详情 | `/api/admin/partner-employee/{id}` | GET | 查询员工详情 |
| 创建员工 | `/api/admin/partner-employee/create` | POST | 供应商负责人使用 |
| 更新员工 | `/api/admin/partner-employee/update` | POST | 供应商负责人使用 |
| 启停员工 | `/api/admin/partner-employee/switch_enabled` | POST | 供应商负责人使用 |
| 员工标签 | `/api/admin/partner-employee/set_tag` | POST | 供应商负责人使用 |
| 需求订单列表 | `/api/admin/requirement-order/list` | POST | 查询本供应商订单 |
| 需求订单详情 | `/api/admin/requirement-order/detail` | GET | 查询订单详情 |
| 普通订单接单 | `/api/admin/requirement-order/approve` | POST | 接受普通需求订单，参数使用 `orderId` |
| 安全产品订单接单 | `/api/admin/requirement-order/approve_product` | POST | 通过“项目成员接单”接受安全产品订单，参数使用 `orderId` |
| 拒单 | `/api/admin/requirement-order/reject` | POST | 拒绝原因必填 |
| 采购单列表 | `/api/admin/purchase-order/partner_orders` | GET | 查询本供应商采购单 |
| 采购单详情 | `/api/admin/purchase-order/partner_order_detail` | GET | 含工时核对结果 |
| 采购响应信息 | `/api/admin/purchase-order/respond_info` | GET | 响应前回填信息 |
| 采购单响应 | `/api/admin/purchase-order/partner_respond` | POST | 提交金额、税率和工程师 |
| 工时列表 | `/api/admin/security-product/work-record/list` | POST | 查询授权范围工时 |
| 工时详情 | `/api/admin/security-product/work-record/detail` | GET | 含编辑历史 |
| 提交工时 | `/api/admin/security-product/work-record/submit` | POST | 工程师或负责人代填 |
| 修改工时 | `/api/admin/security-product/work-record/update` | POST | 变更原因必填 |
| 流程事件 | `/api/admin/security-product/process-event/list` | GET | 供应商负责人查询授权范围事件 |
| 订单材料 | `/api/admin/requirement-order-project-document/list` | GET | 按需求订单查询 |
| 下载材料 | `/api/admin/requirement-order-project-document/download` | GET | 下载授权材料 |

`POST` 接口的字段格式以后端契约为准；部分员工管理接口使用表单编码，其余业务接口通常使用 JSON。

### 3. 员工与订单权限

- 供应商工程师只能访问本人被绑定订单和本人工时；
- 供应商负责人可以访问本供应商订单、采购单、员工和名下工程师工时；
- 工程师不能调用采购单列表、详情和响应接口；
- 工程师不需要调用工时核对结果和流程事件；这两类订单级汇总信息由负责人使用；
- `userId` 表示实际工作工程师，`operatorId/operatorName/operatorRole` 表示实际操作人；
- 请求体中的 ID 不能用于越权访问，服务端必须校验对象归属。

### 4. 需求订单

需求订单列表和详情用于确认订单状态、服务时间、项目、交付状态和工程师绑定关系。供应商负责人确认可承接后调用与订单类型对应的接单接口：普通订单使用 `/api/admin/requirement-order/approve`，安全产品订单使用 `/api/admin/requirement-order/approve_product`（项目成员接单）；拒绝时必须提供原因。

接单、拒单和重新操作前应读取最新详情。已处理订单再次提交应返回状态冲突，客户端不得重复重试。

### 5. 采购单与工时核对

供应商负责人先读取采购单详情和 `respond_info`，确认采购单状态可响应，采购金额、税率、参与工程师正确，交付物已上传，工时核对无阻断问题。

安全产品采购单详情和响应信息返回 `workHourCheck`，关键字段包括：

- `workHourCheckStatus`：总体状态；
- `workHourCheckIssues[]`：结构化问题码；
- `workHourCheckItems[]`：每名工程师明细；
- 工时总小时、折算人天、响应人天和预估人天；
- `deliveryMaterialUploaded`：交付物上传状态；
- `workHourErrorReasonRequired` 和 `workHourErrorReasonOptions[]`。

调用方必须同时读取状态字段和问题列表，不能通过提示文案推断状态。

提交采购单响应时，`partner_respond` 至少包含采购单、金额、税率和参与工程师。若要求误差原因，`workHourErrorReason` 必须取自 `workHourErrorReasonOptions`；必要时传 `workHourErrorReasonDetail`。

重新提交和历史通过 `responseRound`、`supplierResponseHistory[]` 及历史完整性标记区分。旧采购单历史可能不完整，客户端应原样展示，不得伪造。

### 6. 安全产品工时

工时以 `requirementOrderId` 为主要关联对象。核心字段包括 `requirementOrderId`、`userId`、`date`、`workHours`、`status`、`operatorId/operatorName/operatorRole` 和 `confirmedOrderId`。

提交和修改规则：

- `workHours` 是正整数小时，4 小时为半人天，8 小时为一人天；
- `date` 是实际工作日期，不能晚于当天；
- 日期必须落在订单服务开始和结束时间内；
- 同一订单、工程师和日期不能重复填写；
- 修改必须提供原因；
- 可修改状态由服务端校验；
- 详情中的 `editHistory[]` 保留首次填写和后续修改记录。

供应商负责人代填时仍应把实际工程师写入 `userId`，不能把负责人写入该字段。

### 7. 流程事件

`process-event/list` 至少指定 `requirementId`、`requirementOrderId` 或 `purchaseOrderId` 中的一个范围，不允许无条件查询全库。

事件应使用 `eventTime` 排序和计算耗时。典型事件可用于定位需求审批、供应商响应、锁单、采购单创建、首次填工时、采购单响应和审核闭环。

`historyComplete=false` 表示旧数据事件链不完整。禁止使用对象 `updateTime`、创建时间或当前状态反推缺失业务节点时间。

### 8. 交付材料

交付材料按需求订单查询。客户端应只展示和下载当前身份有权限访问的材料。

当前供应商开放能力不包含员工侧交付材料上传、驳回或删除接口。供应商员工在 CLI 中只能查询和下载材料；上传和交付管理由供应商管理员在平台内完成。

下载文件时注意：

- 使用短期授权或当前 AccessToken，不得把下载链接写入日志；
- 文件可能包含客户、项目和技术敏感信息；
- 遵循最小下载、短期保存、访问审计和结果脱敏原则；
- 不要覆盖本地已有文件，除非用户明确确认。

### 9. 错误处理

| HTTP 状态 | 含义 | 建议处理 |
| --- | --- | --- |
| `400` | 参数、值域或业务校验失败 | 根据错误码和错误说明修正后重试 |
| `401` | Token 无效或过期 | 停止自动化并重新认证 |
| `403` | 角色、供应商归属或数据范围无权限 | 停止操作，不更换 ID 试探 |
| `404` | 对象不存在或不可见 | 通过列表查询授权对象 |
| `409` | 状态冲突或重复操作 | 读取最新状态后重新判断 |
| `429` | 请求过频 | 限速并指数退避 |
| `500` | 平台异常 | 保留脱敏请求标识并联系平台研发 |

### 10. 安全要求

- Token 不得写入代码、日志、命令参数、截图或共享文档；
- 不使用共享账号或高权限账号；
- 写操作先查询最新状态，由用户确认后提交；
- 所有权限判断以服务端结果为准，客户端提示不能替代鉴权；
- 不开放内部需求审批、派单、采购单内部审核、全库看板或平台管理接口；
- 无权限时直接停止，不得更换供应商 ID、用户 ID、订单 ID 或 Token 重试。
