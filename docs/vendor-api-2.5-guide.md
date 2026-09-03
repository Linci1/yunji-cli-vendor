# 云集开放 API 使用指南 2.5（供应商版）

> 发布范围：可向已接入云集平台的供应商开放

### 1. 新增能力

2.5 在原有供应商需求订单、采购单和交付材料能力基础上，新增安全产品工时和流程事件接口。

| 接口 | 方法 | 用途 | 适用角色 |
| --- | --- | --- | --- |
| `/api/admin/security-product/work-record/list` | POST | 查询授权范围内工时 | 负责人、工程师 |
| `/api/admin/security-product/work-record/detail` | GET | 查询工时详情和编辑历史 | 负责人、工程师 |
| `/api/admin/security-product/work-record/submit` | POST | 按需求订单提交工时 | 负责人、工程师 |
| `/api/admin/security-product/work-record/update` | POST | 修改允许变更的工时 | 负责人、工程师 |
| `/api/admin/security-product/process-event/list` | GET | 查询授权订单流程事件 | 负责人、工程师 |

### 2. 工时关联与权限

- 工时以 `requirementOrderId` 为主要关联对象；
- `userId` 表示实际填报工程师；
- `operatorId/operatorName/operatorRole` 表示实际操作人；
- 工程师只能操作本人有权访问的订单和本人工时；
- 负责人只能操作本供应商名下工程师及本供应商订单；
- 服务端必须校验订单、工程师绑定关系、日期范围和重复工时。

### 3. 工时核对

供应商采购单详情和响应信息增加 `workHourCheck`：

- 工时总小时及折算人天；
- 采购响应人天和预估人天；
- 工时填写与审核完成状态；
- 交付物上传状态；
- 每名工程师核对明细；
- 结构化问题码；
- 误差原因是否必填及可选原因。

调用方必须同时读取 `workHourCheckStatus` 和 `workHourCheckIssues[]`，不能通过提示文案推断状态。

### 4. 采购单响应

`POST /api/admin/purchase-order/partner_respond` 增加：

- `workHourErrorReason`：工时误差原因；
- `workHourErrorReasonDetail`：补充说明。

若 `workHourErrorReasonRequired=true`，原因必须从 `workHourErrorReasonOptions` 中选择。供应商响应、重新提交和审核历史通过 `responseRound`、`supplierResponseHistory[]` 和历史完整性标记区分。

### 5. 流程事件

流程事件接口至少指定需求单、需求订单或采购单中的一个范围。供应商仅可读取本供应商或本人订单相关事件。

业务耗时应使用 `eventTime`。`historyComplete=false` 表示旧数据无法完整还原，禁止使用对象 `updateTime` 推断流程时间。

### 6. 安全要求

- 每位用户使用自己的 AccessToken；
- Token 不得写入代码、日志、命令参数或共享文档；
- 写操作必须由用户确认，并保留操作者和修改历史；
- 无权限时不更换其他 ID 试探；
- 本指南不开放内部需求审批、派单、采购单内部审核、全库看板或平台管理接口。
