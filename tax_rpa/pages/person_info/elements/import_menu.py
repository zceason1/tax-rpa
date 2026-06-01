from tax_rpa.pages.person_info.elements.targets import TextTarget


IMPORT_BUTTON = TextTarget(
    text="\u5bfc\u5165",
    screenshot_name="person_info_import_button",
)

SUBMIT_DATA_BUTTON = TextTarget(
    text="\u63d0\u4ea4\u6570\u636e",
    screenshot_name="person_info_submit_data_button",
)

IMPORT_FILE_OPTIONS = (
    TextTarget(
        text="\u5bfc\u5165\u6587\u4ef6",
        screenshot_name="person_info_import_file_option",
    ),
    TextTarget(
        text="\u6807\u51c6\u6a21\u677f\u5bfc\u5165",
        screenshot_name="person_info_standard_template_import_option",
    ),
)
