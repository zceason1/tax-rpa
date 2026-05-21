# 自然人电子税务局扣缴端 RPA 组件化架构

## 1. 文档目标

本文档说明 `rpa-tax-poc` 当前以 `tax_rpa` 为主包的组件化架构、Driver 封装规则、运行链路和后续扩展方式。

当前项目边界：

- 核心代码全部收口到 `tax_rpa/` 包内。
- 主流程 CLI 入口是 `tax_rpa.cli.from_zero_import_person_info`。
- 页面调试 CLI 入口是 `tax_rpa.cli.debug_person_info_page`。
- 配置模型和安全校验位于 `tax_rpa.config.person_import`。
- 根目录不再保留业务 Python 脚本，只保留 `.cmd` 启动器；`.cmd` 不维护业务默认值。
- 当前流程只覆盖“人员信息采集 -> 导入 -> 导入文件 -> 选择文件”。
- 当前流程不包含报送、申报、缴款等高风险动作。

## 2. 当前目录结构

```text
rpa-tax-poc/
  run_from_zero_import_person_info.cmd  # Windows 启动器，固定使用 .venv

  tax_rpa/
    cli/
      from_zero_import_person_info.py   # CLI：参数、提权、加载配置、启动工作流
      debug_person_info_page.py         # CLI：快速调试人员信息采集页

    config/
      person_import.py                  # 配置模型、路径校验、安全动作校验

    app/
      tax_client_app.py                 # 启动/复用客户端，等待登录主窗口
      main_shell.py                     # 主框架，打开业务页面

    pages/
      person_info_page.py               # 人员信息采集页

    components/
      left_nav.py
      toolbar.py
      import_dropdown.py
      file_dialog.py
      message_dialog.py
      import_result.py

    drivers/
      win32_driver.py
      ocr_driver.py
      mouse_driver.py
      region_driver.py
      wait_driver.py
      logger.py

    runtime/
      context.py
      result.py

    workflows/
      import_person_info_workflow.py

  tests/
  docs/
  config/
  data/
```

## 3. 运行方式

完整流程可以使用根目录 `.cmd`，它只负责固定调用 `.venv\Scripts\python.exe` 并转发参数：

```powershell
.\run_from_zero_import_person_info.cmd
```

带参数运行：

```powershell
.\run_from_zero_import_person_info.cmd --config .\config\person_import.json
```

也可以直接以模块方式运行：

```powershell
.\.venv\Scripts\python.exe -m tax_rpa.cli.from_zero_import_person_info --config .\config\person_import.json
```

`.cmd` 不是业务入口本身，不应在里面维护配置路径、页面名称、等待时间或导入步骤。这些逻辑都应放在 `tax_rpa/` 包内。

快速调试页面逻辑时，推荐直接使用页面调试 CLI：

```powershell
.\.venv\Scripts\python.exe -m tax_rpa.cli.debug_person_info_page inspect --config .\config\person_import.json --timeout 20
.\.venv\Scripts\python.exe -m tax_rpa.cli.debug_person_info_page open --config .\config\person_import.json --timeout 20
.\.venv\Scripts\python.exe -m tax_rpa.cli.debug_person_info_page import-flow --config .\config\person_import.json --timeout 20
```

三个动作的用途：

- `inspect`：连接已打开客户端，检查当前是否能识别人员信息采集页。
- `open`：连接已打开客户端，执行进入人员信息采集页的页面逻辑。
- `import-flow`：执行打开页面和导入流程，默认 `dry-run`，不会真正提交文件对话框。

调试参数：

- `--launch`：当客户端未运行且配置了 `app_path` 时，由脚本启动客户端。
- `--submit`：仅对 `import-flow` 生效，允许真正提交文件选择框。
- `--timeout`：缩短单页调试等待时间，避免调试时长时间卡住。

VS Code 调试入口位于 `.vscode/launch.json`，同样使用模块方式。完整流程使用：

```text
module = tax_rpa.cli.from_zero_import_person_info
python = .venv\Scripts\python.exe
```

页面级调试使用：

```text
module = tax_rpa.cli.debug_person_info_page
args = inspect / open / import-flow
```

## 4. 主运行链路

```text
tax_rpa.cli.from_zero_import_person_info
  -> load_import_config()
  -> 如未管理员运行，则使用 ShellExecuteW runas 自提权
  -> ImportPersonInfoWorkflow.run()
    -> TaxClientApp.start_if_needed()
    -> TaxClientApp.wait_for_login()
    -> MainShell.open_person_info_page()
    -> PersonInfoPage.import_person_file()
      -> 关闭提示弹窗
      -> 点击导入按钮
      -> 选择导入文件菜单
      -> 选择人员信息文件
      -> 等待导入结果
```

业务流程保持语义化：

```python
app.start_if_needed()
app.wait_for_login()

shell = app.shell()
person_page = shell.open_person_info_page()
person_page.import_person_file(config.person_info_file)
```

业务流程中不应散落 OCR、坐标、鼠标、窗口枚举和固定 `sleep`。

## 5. 分层设计

当前分层借鉴前端组件化思想：

```text
App
  Shell
    Page
      Component
        Driver
```

对应到当前项目：

```text
TaxClientApp
  MainShell
    PersonInfoPage
      LeftNavComponent
      ToolbarComponent
      ImportDropdownComponent
      FileDialogComponent
      MessageDialogComponent
        Win32Driver
        OcrDriver
        MouseDriver
        RegionDriver
        WaitDriver
        RunLogger
```

职责边界：

- `Workflow` 只描述业务顺序。
- `App` 负责客户端生命周期。
- `Shell` 负责主框架和页面入口。
- `Page` 代表业务页面。
- `Component` 代表页面内可复用功能块。
- `Driver` 封装底层技术。
- `runtime` 保存共享上下文和统一结果模型。
- `config` 保存配置模型、加载和安全校验。
- `cli` 保存命令行入口。

## 6. CLI 和配置

CLI 文件：

```text
tax_rpa/cli/from_zero_import_person_info.py
tax_rpa/cli/debug_person_info_page.py
```

`from_zero_import_person_info.py` 职责：

- 解析命令行参数。
- 检查管理员权限。
- 必要时使用 `ShellExecuteW runas` 自提权。
- 加载 `config/person_import.json`。
- 创建 `RunLogger`。
- 执行 `ImportPersonInfoWorkflow`。

`debug_person_info_page.py` 职责：

- 复用同一份 `config/person_import.json`。
- 连接已运行客户端或按需启动客户端。
- 使用较短 timeout 快速调试单个 Page。
- 支持 `inspect`、`open`、`import-flow` 三种页面动作。
- `import-flow` 默认强制 `dry-run`，避免调试时误提交。
- 继续复用管理员权限自提权逻辑。

配置文件：

```text
tax_rpa/config/person_import.py
```

职责：

- `PersonImportConfig`：人员导入流程配置模型。
- `load_import_config()`：读取 JSON 配置。
- `validate_excel_path()`：校验人员 Excel 文件。
- `validate_app_path()`：校验客户端路径。
- `assert_safe_action()`：拦截高风险动作。

所有包内代码应从 `tax_rpa.config.person_import` 导入配置能力。

## 7. Driver 层设计

Driver 层只解决“怎么做”，不表达税务业务语义。

### Win32Driver

负责 Windows 窗口、控件、前台切换和文件对话框。

主要能力：

- 使用 `psutil` 查找扣缴端进程。
- 使用 Win32 API 枚举顶层窗口和子控件。
- 主窗口优先匹配 `Tfrm_MainFrame`。
- 文件选择框优先匹配标准对话框 `#32770`。
- 使用 `SetForegroundWindow`、`BringWindowToTop`、`AttachThreadInput` 提高前台切换成功率。
- 使用 `WM_SETTEXT` 向文件路径输入框写入路径。

组件和页面必须优先依赖 `Win32Driver` 实例方法。

### OcrDriver

负责截图、OCR 识别、文本匹配和 OCR 点击点计算。

核心链路：

```text
截图指定区域
  -> OCR 识别文字
  -> 筛选目标文本
  -> 计算文字框中心点
  -> 转换为屏幕坐标
  -> 调用 MouseDriver.click()
```

### MouseDriver

负责真实鼠标移动和点击。

点击链路：

```text
SetCursorPos
  -> GetCursorPos 校验
  -> mouse_event LEFTDOWN
  -> mouse_event LEFTUP
```

这是当前客户端点击生效的关键方式。

### RegionDriver

负责从主窗口和子控件中推断 OCR 区域，例如左侧导航区和右侧内容区。

### WaitDriver

负责条件等待。它等待“结果出现”，不依赖固定 `sleep` 作为主判断方式。

### RunLogger

负责运行证据。

主要能力：

- 每次运行创建 `artifacts/person_import_时间戳/`。
- 使用 `steps.jsonl` 保存步骤日志。
- 使用 `step()` 上下文管理器记录类似 `allure.step` 的步骤开始、成功、失败和耗时。
- 保存 OCR rows、summary、failed 等结构化数据。
- 保存关键截图。

示例：

```python
with logger.step("点击导入按钮", page="person_info_page"):
    toolbar.click_button("导入")
```

## 8. Driver 注入规则

组件和页面不应直接 import 一组底层 Win32 helper 函数，而应依赖 `Win32Driver` 实例。

推荐写法：

```python
class FileDialogComponent:
    def __init__(
        self,
        dialog: dict[str, Any],
        logger: Any,
        dry_run: bool,
        mouse: MouseDriver | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        self.mouse = mouse or MouseDriver()
        self.win32 = win32 or Win32Driver()
```

不推荐写法：

```python
from tax_rpa.drivers.win32_driver import collect_children, set_window_text
```

原因：

- 组件应依赖 Driver 服务实例。
- 注入 Driver 后更容易做单元测试。
- 后续替换 Win32 实现时，不需要改组件业务代码。

## 9. Page 层设计

`PersonInfoPage.import_person_file()` 当前按业务步骤组织：

```text
关闭提示弹窗
点击导入按钮
选择导入文件菜单
选择人员信息文件
等待导入结果
```

每个步骤都通过 `self._step(...)` 包装。真实运行时写入 `RunLogger.step()` 日志；测试或无上下文场景下退化为空上下文。

Page 可以持有 Driver 实例，但不应把底层操作散落在业务方法里。可复用能力应优先下沉到 Component 或 Driver。

## 10. 安全策略

所有会触发点击或提交的动作文本必须经过 `assert_safe_action()`。

当前默认禁止的高风险关键词：

```text
报送
发送申报
申报
缴款
缴纳
税款缴纳
```

后续如果要支持这些动作，不能直接放开通用校验。应新增单独配置、单独审批和单独测试。

## 11. 测试策略

当前测试重点覆盖：

- 配置解析和路径校验。
- 禁止动作校验。
- 启动决策。
- OCR 匹配排序。
- 鼠标误差判断。
- 文件对话框按钮匹配。
- 弹窗识别。
- 页面和工作流的组件编排。
- Driver 注入边界。
- 页面调试 CLI 的 timeout 和 dry-run 行为。
- `RunLogger.step()` 的 start、passed、failed 日志行为。
- `PersonInfoPage.import_person_file()` 的业务步骤顺序。

本地验证命令：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 12. 新增页面的方式

新增页面时，应优先复用现有组件：

```python
class SomeBusinessPage:
    def open(self):
        return LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
        ).open_page("页面名称", ready_check=self.is_ready)

    def import_file(self, path):
        self.toolbar.click_button("导入")
        self.import_dropdown.choose_item("导入文件")
        return self.file_dialog.choose_file(path)
```

新增页面通常只需要实现：

- 页面 ready 判断。
- 页面专属业务动作。
- 页面专属结果判断。

不要重复实现：

- Win32 窗口枚举。
- OCR 截图和匹配。
- 鼠标移动和点击。
- 文件选择框填充。
- 通用弹窗关闭。
- 日志和截图保存。

## 13. 后续优化方向

当前架构方向已经稳定，后续优化建议按低风险顺序推进：

- 抽象 `Rect`、`Point`、`WindowInfo`、`OcrMatch` 数据结构。
- 将文件选择框能力进一步收口为 `FileDialogDriver` 或保留在 `Win32Driver` 的子能力中。
- 为 OCR 点击策略增加更多单元测试。
- 增加统一异常类型，例如 `WindowNotFoundError`、`OcrTargetNotFoundError`、`MouseMoveError`。

不建议现在做大规模重写。当前更适合继续做边界收口和测试增强。

## 14. 维护原则

- `tax_rpa/` 是主包，业务 Python 代码应放入包内。
- 根目录只保留启动器、配置、数据、文档和工程文件。
- `.cmd` 只负责选择 `.venv` 并转发参数，不负责维护业务默认值。
- 调试单个页面时优先新增或复用 `tax_rpa.cli.debug_*` 入口，不新增根目录临时脚本。
- 能复用 Component 的，不新增页面内底层代码。
- 能复用 Driver 的，不重复写 Win32、OCR、鼠标逻辑。
- 能通过 ready check 判断的，不依赖固定坐标和固定 `sleep`。
- 能记录证据的步骤，都写入截图或 JSON。
- 废弃文件及时删除，不保留无调用方的兼容脚本。
