# Windows RPA 驱动层导读

驱动层负责“如何操作 Windows 和界面”。它不关心税务业务，只关心窗口、控件、截图、OCR、鼠标和键盘。

## Win32Driver

文件：`tax_rpa/drivers/win32_driver.py`

主要能力：

- 按进程名查找 PID。
- 枚举顶层窗口和子控件。
- 获取窗口标题、类名、矩形、PID。
- 查找主窗口。
- 把窗口切到前台。
- 查找文件选择框。
- 给文件路径输入框写入路径。
- 查找按钮并点击。
- 终止客户端进程。

需要掌握的 Windows 概念：

- `hwnd`：窗口句柄，Windows UI 自动化的核心定位对象。
- `pid`：进程 ID，用来判断窗口属于哪个进程。
- `rect`：窗口坐标 `[left, top, right, bottom]`。
- `class name`：窗口或控件类型，例如标准文件对话框常见为 `#32770`。

## OcrDriver

文件：`tax_rpa/drivers/ocr_driver.py`

完整链路：

```text
截图指定区域
  -> 保存截图
  -> 调用 OCR 引擎
  -> 得到文本、置信度、文字框
  -> 匹配目标文本
  -> 计算文字框中心
  -> 转换为屏幕鼠标坐标
  -> 调用 MouseDriver.click()
```

你需要重点理解：

- `ocr_rect()`：截图并读取 OCR 文本。
- `find_best_ocr_match()`：从 OCR 行里找最佳目标。
- `box_center()`：计算文字框中心点。
- `_coordinate_transform()`：处理截图尺寸和鼠标屏幕尺寸差异。
- `click_text()`：把识别到的文字转成真实点击。

OCR 是 RPA 稳定性的关键风险点。新增功能时，必须为结果识别和文本匹配写测试。

## UiaDriver

文件：`tax_rpa/drivers/uia_driver.py`

作用：

- 通过 UI Automation 查找控件。
- 尝试 `invoke()` 或 `select()`。
- 尝试聚焦输入框。

当前登录组件会优先尝试 UIA。如果 UIA 找不到，再回退 OCR 点击。

## MouseDriver

文件：`tax_rpa/drivers/mouse_driver.py`

作用：

- 把普通屏幕坐标转成 Windows 绝对鼠标坐标。
- 移动鼠标。
- 点击。
- 校验鼠标是否移动到预期位置。

新增功能时，不要在业务代码里直接使用 `mouse_event`。应该通过 `MouseDriver` 或现有 component 调用。

## RegionDriver

文件：`tax_rpa/drivers/region_driver.py`

作用：

- 根据主窗口和子控件推断左侧导航区域。
- 推断右侧内容区域。
- 给 OCR 提供更稳定的截图范围。

如果 OCR 经常识别到无关文字，优先检查截图区域是否过大或区域判断是否错误。

## WaitDriver

文件：`tax_rpa/drivers/wait_driver.py`

作用：

- 等待某个条件成立。
- 减少固定 `sleep`。

RPA 代码里应优先等待“状态出现”，而不是盲目等待固定秒数。

## RunLogger

文件：`tax_rpa/drivers/logger.py`

作用：

- 记录运行步骤。
- 保存截图。
- 保存 OCR rows。
- 保存 summary 和 failed 文件。

调试真实客户端时，先看日志和截图，再改代码。

## 常见问题定位

| 现象 | 优先检查 |
|------|----------|
| 找不到主窗口 | `process_name`、PID、主窗口类名、管理员权限 |
| 点击错位置 | OCR 截图、坐标缩放、DPI、窗口是否前台 |
| OCR 找不到文字 | 截图区域、阈值、文字别名、界面缩放 |
| 文件对话框没填入路径 | 对话框 `hwnd`、edit 控件、打开按钮文本 |
| 登录失败 | UIA 是否能找到控件、OCR fallback 截图、密码配置 |
