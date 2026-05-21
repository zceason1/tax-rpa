# RPA 页面步骤化架构设计

## 1. 目标

本文档描述 `tax_rpa` 后续推荐采用的页面步骤化架构。

核心目标是让代码结构贴近真实业务操作路径：底层 Driver 负责 Windows、OCR、鼠标等技术动作；页面目录按照左侧菜单栏划分；页面内再拆分元素识别、页面组件、业务步骤；最后由 Workflow 组装完整业务流程。

这套结构重点解决三个问题：

- 页面越来越多后，组件和元素识别规则不再混在全局目录里。
- OCR 文本、窗口类名、区域推断、按钮识别等信息集中维护。
- Workflow 只表达业务顺序，不直接接触坐标、OCR、窗口句柄或弹窗细节。

## 2. 核心思想

这套架构遵循三条核心思想：

- 元素集中：所有页面识别信息集中放在 `elements/`，包括 OCR 文本、窗口类名、按钮别名、区域规则和结果判定文本。
- 页面动作语义化：Page、Component 和 Step 暴露的是业务动作名称，例如 `open_page()`、`choose_file()`、`import_person_file()`，而不是 `click(x, y)` 或 `find_text()`。
- 用例只编排：Workflow 只负责串联业务步骤，不直接写 OCR、鼠标、窗口、坐标、弹窗识别等实现细节。

判断一段代码应该放在哪里，可以用这三个问题：

- 它是在描述“识别什么”吗？如果是，放到 `elements/`。
- 它是在表达“对页面做什么业务动作”吗？如果是，放到 Page、Component 或 Step。
- 它是在说明“业务步骤按什么顺序执行”吗？如果是，放到 Workflow。

## 3. 总体分层

推荐依赖方向如下：

```text
workflows
  -> page steps
    -> page / subpage
      -> page-owned components
        -> elements
          -> drivers
```

含义：

- `drivers` 负责底层控制能力，例如点击、OCR、窗口枚举、区域推断、等待。
- `elements` 负责集中描述界面元素的识别信息，不执行动作。
- `components` 负责复用页面内或跨页面的操作能力。
- `page` 代表一个左侧菜单对应的业务页面。
- `steps` 代表一个语义化的可复用业务步骤。
- `workflows` 只负责编排多个业务步骤，形成完整自动化流程。

## 4. 推荐目录结构

```text
tax_rpa/
  drivers/
    mouse_driver.py
    ocr_driver.py
    win32_driver.py
    region_driver.py
    wait_driver.py
    logger.py

  pages/
    shared/
      elements/
        common_dialogs.py
        main_shell.py
      components/
        left_nav.py
        toolbar.py
        file_dialog.py
        message_dialog.py

    person_info/
      page.py
      elements/
        page_markers.py
        toolbar.py
        import_menu.py
        import_result.py
      components/
        import_dropdown.py
      steps/
        open_page.py
        import_person_file.py
        wait_import_result.py

  workflows/
    import_person_info_workflow.py
```

目录说明：

- `pages/shared/` 放跨页面共享能力，例如左侧菜单、通用工具栏、文件选择框、通用弹窗。
- `pages/person_info/` 放“人员信息采集”页面专属能力。
- `elements/` 只保存元素识别规则和目标定义。
- `components/` 保存可复用动作单元。
- `steps/` 保存业务步骤，供 Workflow 编排。

## 5. Driver 层职责

Driver 层只解决“怎么操作系统和界面”，不表达税务业务语义。

典型职责：

- `Win32Driver`：窗口枚举、窗口文本、控件查找、前台切换、文件对话框操作。
- `OcrDriver`：截图、OCR 识别、文本匹配、OCR 点击点计算。
- `MouseDriver`：真实鼠标移动和点击。
- `RegionDriver`：根据窗口和控件推断导航区、内容区、弹窗区域。
- `WaitDriver`：条件等待，减少固定 `sleep`。
- `RunLogger`：步骤日志、截图、OCR 结果、失败证据。

Driver 层不应 import `pages`、`components`、`steps` 或 `workflows`。

## 6. Elements 层职责

Elements 层描述“识别什么”，不执行点击、等待或业务判断。

元素集中是本架构的基础。只要一个识别规则会被页面、组件或步骤使用，就应该优先沉淀到 `elements/`，而不是写在调用处。

可以保存的信息：

- 页面标题或关键 OCR 文本。
- 按钮文本和候选别名。
- 窗口类名，例如 `#32770`。
- 控件 class name、title、role。
- 页面区域识别规则。
- OCR 匹配阈值或页面级覆盖策略。
- 成功、失败、未知结果的判定文本。

推荐把元素定义成结构化对象，而不是散落的字符串常量。

示例：

```python
PERSON_INFO_PAGE_MARKER = TextTarget(
    text="人员信息采集",
    screenshot_name="person_info_page_marker",
)

IMPORT_BUTTON = TextTarget(
    text="导入",
    aliases=("导 入",),
    screenshot_name="person_info_import_button",
)
```

Elements 层可以被 `components` 和 `steps` 使用，但不应依赖 Driver 实例。

## 7. Components 层职责

Components 层表示可复用的界面操作能力。

组件方法应该以页面动作命名，让调用方读到的是“做什么”，而不是底层“怎么点、怎么找”。

组件可以依赖：

- Driver 实例。
- Elements 定义。
- Logger。
- Config。
- Runtime context。

组件不应该直接编排完整业务流程。

例如：

- `ToolbarComponent.click_button()` 只负责点击工具栏按钮。
- `FileDialogComponent.choose_file()` 只负责选择文件。
- `MessageDialogComponent.close_if_present()` 只负责关闭通用弹窗。
- `ImportDropdownComponent.choose_item()` 只负责选择导入菜单项。

组件是否放入 `shared`，取决于是否跨页面复用。

推荐规则：

- 多个页面会用到的组件，放在 `pages/shared/components/`。
- 只服务某个页面的组件，放在该页面目录下的 `components/`。

## 8. Page 层职责

Page 层代表一个左侧菜单栏对应的业务页面。

Page 应该负责：

- 保存页面窗口句柄和上下文。
- 判断页面是否 ready。
- 创建页面专属组件。
- 暴露少量页面级能力。

Page 不应该承载太多业务步骤细节。

Page 对外暴露的能力应该保持语义化，例如打开页面、判断 ready、获取工具栏、获取导入菜单，而不是暴露坐标、截图或 OCR rows。

推荐写法：

```python
class PersonInfoPage:
    def is_ready(self) -> bool:
        ...

    def toolbar(self) -> ToolbarComponent:
        ...

    def import_dropdown(self) -> ImportDropdownComponent:
        ...
```

如果一个方法内部已经包含多个业务动作，例如“关闭弹窗 -> 点击导入 -> 选择菜单 -> 选择文件 -> 等待结果”，应该优先拆到 `steps/`。

## 9. Steps 层职责

Steps 层表示一个可复用的业务步骤。

业务步骤应该有清晰的输入、输出和失败状态。

Step 是页面动作语义化的主要承载位置。一个 Step 应该对应用户能理解的业务动作，而不是底层技术动作。

示例：

```text
open_person_info_page
import_person_file
wait_import_result
```

每个 Step 可以：

- 调用 Page。
- 调用 Page-owned Component。
- 调用 Shared Component。
- 返回 `StepResult`。
- 写入结构化日志。

Step 不应该：

- 直接调用底层 Win32 API。
- 直接散落 OCR 文本常量。
- 直接维护复杂坐标计算。
- 直接决定完整 Workflow 的顺序。

示例结构：

```python
class ImportPersonFileStep:
    def __init__(self, page: PersonInfoPage) -> None:
        self.page = page

    def run(self, file_path: Path) -> StepResult:
        ...
```

## 10. Workflow 层职责

Workflow 只负责编排业务步骤顺序。

它应该读起来像业务说明，而不是技术脚本。

用例只编排是 Workflow 的边界。Workflow 不判断元素怎么找，也不决定按钮怎么点；这些细节由 Step、Component、Element 和 Driver 分层处理。

推荐表达：

```python
app.start_if_needed()
app.wait_for_login()

page = OpenPersonInfoPageStep(shell).run()
ImportPersonFileStep(page).run(config.person_info_file)
WaitImportResultStep(page).run()
```

Workflow 不应该直接出现：

- OCR 匹配。
- 鼠标点击。
- 窗口枚举。
- 固定坐标。
- 文件对话框控件细节。
- 弹窗 class name。

## 11. Import 方向规则

建议约束 import 方向：

```text
drivers
  不 import pages/components/steps/workflows

elements
  不 import drivers/workflows

components
  可以 import drivers/elements/runtime/config

page
  可以 import shared components/page components/elements

steps
  可以 import page/components/runtime

workflows
  可以 import app/config/runtime/steps
  不直接 import drivers/elements
```

这条规则可以避免底层能力反向依赖业务层，也能让单元测试更容易编写。

## 12. 人员信息采集页面示例

以“人员信息采集 -> 导入人员信息文件”为例，推荐拆分如下：

```text
pages/person_info/
  page.py

  elements/
    page_markers.py
    import_menu.py
    import_result.py

  components/
    import_dropdown.py

  steps/
    open_page.py
    import_person_file.py
    wait_import_result.py
```

职责划分：

- `page_markers.py`：定义“人员信息采集”等页面 ready 识别规则。
- `import_menu.py`：定义“导入”“导入文件”等菜单元素。
- `import_result.py`：定义成功、失败、未知结果识别规则。
- `page.py`：封装 `PersonInfoPage`，提供 `is_ready()` 和组件创建能力。
- `import_dropdown.py`：封装导入菜单选择逻辑。
- `open_page.py`：通过左侧菜单打开人员信息采集页面。
- `import_person_file.py`：点击导入、选择导入文件、填入文件路径。
- `wait_import_result.py`：等待并分类导入结果。

对应 Workflow：

```python
class ImportPersonInfoWorkflow:
    def run(self) -> WorkflowResult:
        app.start_if_needed()
        app.wait_for_login()

        page = OpenPersonInfoPageStep(app.shell()).run()
        import_file = ImportPersonFileStep(page).run(config.person_info_file)
        import_result = WaitImportResultStep(page).run()

        return WorkflowResult.from_steps([import_file, import_result])
```

## 13. 测试策略

测试重点应该覆盖边界，而不是只覆盖 happy path。

推荐测试范围：

- Driver 注入是否生效，Step 测试不依赖真实鼠标和真实窗口。
- Elements 中的文本、别名、结果分类是否正确。
- Component 是否按预期调用 Driver。
- Page ready 判断是否基于元素定义。
- Step 是否按正确顺序调用 Page 和 Component。
- Workflow 是否只编排步骤，不直接调用底层 Driver。
- 失败时是否返回清晰的 `StepResult.status` 和证据。

可以逐步增加架构约束测试，例如禁止 `workflows/` 直接 import `tax_rpa.drivers`。

## 14. 迁移策略

不建议一次性重构所有目录。

推荐按低风险顺序迁移：

1. 保留现有行为和测试，先新增 `pages/person_info/` 目录。
2. 把人员信息采集相关常量迁入 `pages/person_info/elements/`。
3. 把页面 ready 判断迁入 `pages/person_info/page.py`。
4. 把 `import_person_file()` 拆为 `steps/import_person_file.py` 和 `steps/wait_import_result.py`。
5. 将跨页面组件移动到 `pages/shared/components/`。
6. 修改 Workflow，让它调用 Step，而不是直接调用页面大方法。
7. 增加 import 边界测试，防止后续代码重新耦合。

迁移过程中，每一步都应保持现有测试通过。

## 15. 命名建议

目录命名：

- 页面目录使用业务英文名，例如 `person_info`、`tax_declaration`。
- 通用能力放在 `shared`。
- 业务步骤放在 `steps`。
- 元素定义放在 `elements`。

类命名：

- Page：`PersonInfoPage`
- Step：`ImportPersonFileStep`
- Component：`ImportDropdownComponent`
- Element target：`TextTarget`、`WindowTarget`、`DialogTarget`

结果命名：

- Step 返回 `StepResult`。
- Workflow 返回 `WorkflowResult`。
- `status` 使用稳定英文枚举值，例如 `ok`、`not_ready`、`file_dialog_missing`、`timeout`。

## 16. 维护原则

- Workflow 读起来应该像业务流程。
- Step 读起来应该像一个业务动作。
- Page 只代表页面，不承担完整业务流程。
- Component 负责可复用界面动作。
- Elements 保存识别规则，不执行动作。
- Driver 只解决底层技术问题。
- 元素要集中，页面动作要语义化，用例只做编排。
- 跨页面复用能力放 `shared`，页面专属能力放页面目录。
- 界面变化优先修改 `elements`，不要优先修改 Workflow。
- 新增页面时，先按左侧菜单创建页面目录，再补元素、组件和步骤。
