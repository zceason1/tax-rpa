from tax_rpa.pages.person_info.elements.targets import TextTarget


IMPORT_BUTTON = TextTarget(
    text="导入",
    screenshot_name="person_info_import_button",
)

SUBMIT_DATA_BUTTON = TextTarget(
    text="提交数据",
    screenshot_name="person_info_submit_data_button",
)

IMPORT_FILE_OPTIONS = (
    TextTarget(
        text="导入文件",
        screenshot_name="person_info_import_file_option",
    ),
    TextTarget(
        text="标准模板导入",
        screenshot_name="person_info_standard_template_import_option",
    ),
)
