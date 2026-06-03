# 新 RPA 流程开发检查清单

## 1. 业务目标

- 流程名称：
- 所属页面：
- 运行模式：
- 是否会修改数据：
- 是否会上传文件：
- 是否可能点击提交/申报/缴款：

## 2. 输入材料

- 配置字段：
- manifest 字段：
- 文件角色：
- 文件后缀限制：
- SHA-256 是否需要校验：

## 3. 页面元素

| 元素 | 文本/类名 | 文件位置 | 备注 |
|------|-----------|----------|------|
| 页面 ready 标识 | | `pages/<page>/elements` | |
| 按钮 | | `pages/<page>/elements` | |
| 菜单项 | | `pages/<page>/elements` | |
| 成功结果文本 | | `pages/<page>/elements` | |
| 失败结果文本 | | `pages/<page>/elements` | |

## 4. 页面和组件

- 是否复用 `ToolbarComponent`：
- 是否复用 `ContentTextComponent`：
- 是否复用 `FileDialogComponent`：
- 是否需要新增页面专属 component：
- 是否需要新增 shared component：

## 5. Step 设计

| Step | 输入 | 输出 `status` | 副作用 | 重试策略 |
|------|------|---------------|--------|----------|
| | | | | |

## 6. Workflow 设计

```text
WorkflowName
  -> Step 1
  -> Step 2
  -> Step 3
```

失败停止规则：

- 哪些状态必须停止：
- 哪些状态可以继续：
- 哪些状态表示业务 blocked：

## 7. 安全策略

- `inspect_only` 下是否允许：
- `execute_no_send` 下是否允许：
- `submit` 下是否允许：
- 是否需要一次性 permit：
- 是否需要 production gate：

## 8. 可观测性

- 需要记录哪些截图：
- 需要保存哪些 OCR JSON：
- 失败包需要包含哪些证据：
- callback payload 是否需要新增字段：

## 9. 测试计划

- 成功路径：
- 业务失败：
- OCR 未识别：
- 文件缺失：
- 文件对话框缺失：
- `inspect_only` 拒绝：
- 高风险动作无 permit 拒绝：
- JobRunner 集成：

## 10. 真实客户端校准

- 页面截图：
- OCR rows：
- 成功结果样本：
- 失败结果样本：
- 弹窗样本：
- canary 记录：
- 操作员审核：
