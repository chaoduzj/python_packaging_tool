"""
Python打包工具 - 版本信息

统一管理应用程序的版本号和相关元数据信息，方便修改维护。
"""

# 版本号
__version__ = "1.6.3"
VERSION = __version__

# 构建日期（用于显示，不参与Windows文件版本号）
BUILD_DATE = "20260818"

# 完整显示版本（用于UI显示）
DISPLAY_VERSION = f"{__version__}.{BUILD_DATE}"

# 版本号元组，方便比较
VERSION_TUPLE = tuple(int(x) for x in __version__.split("."))

# 应用程序信息
APP_NAME = "Python脚本打包工具"
APP_NAME_EN = "Python Packaging Tool"
APP_NOTICE = "免费软件，禁止贩卖！"
APP_TITLE = f"{APP_NAME} v{DISPLAY_VERSION}  - {APP_NOTICE}"

# 作者信息
AUTHOR = "徽哥"
AUTHOR_EMAIL = "love-left@qq.com"

# 版权信息
COPYRIGHT = f"Copyright © 2026 {AUTHOR}"
DESCRIPTION = "一个简单易用的Python脚本打包工具，支持PyInstaller和Nuitka两种打包方式。"
DESCRIPTION_EN = (
    "A simple and easy-to-use Python script packaging tool, supporting PyInstaller and Nuitka packing methods."
)

# 自述信息
ABOUT_TEXT = ""
# ABOUT_TEXT = "可有偿提供各种python脚本定制、修改等服务。"

# 是否在反馈弹框中显示捐赠用户专属特权说明
SHOW_VIP_PRIVILEGE = True

# 项目链接（可选）
PROJECT_URL = ""
ISSUE_URL = ""

# 捐赠对话框弹出规则（按软件启动次数触发）
# - DONATE_PROMPT_INITIAL_COUNTS：前几次启动时弹出的固定次数（如第 5、10 次）
# - DONATE_PROMPT_INTERVAL：超过初始次数后的周期（如每 10 次启动弹出一次）
# 修改这两个值即可调整弹出频率，无需改动 GUI 代码。
DONATE_PROMPT_INITIAL_COUNTS = [5, 10]
DONATE_PROMPT_INTERVAL = 10


def should_show_donate_dialog(launch_count: int) -> bool:
    """根据启动次数判断是否应弹出捐赠对话框。

    Args:
        launch_count: 当前启动次数（已递增后的值）

    Returns:
        是否应弹出捐赠对话框
    """
    if launch_count in DONATE_PROMPT_INITIAL_COUNTS:
        return True
    # 超过初始次数后按周期触发（避免与 initial_counts 重复判断）
    max_initial = max(DONATE_PROMPT_INITIAL_COUNTS, default=0)
    if launch_count > max_initial and DONATE_PROMPT_INTERVAL > 0:
        return launch_count % DONATE_PROMPT_INTERVAL == 0
    return False


def get_version() -> str:
    """获取版本号字符串"""
    return __version__


def get_version_tuple() -> tuple:
    """获取版本号元组"""
    return VERSION_TUPLE


def get_app_info() -> dict:
    """获取应用程序完整信息"""
    return {
        "version": DISPLAY_VERSION,
        "version_tuple": VERSION_TUPLE,
        "app_name": APP_NAME,
        "app_name_en": APP_NAME_EN,
        "app_title": APP_TITLE,
        "author": AUTHOR,
        "author_email": AUTHOR_EMAIL,
        "copyright": COPYRIGHT,
        "description": DESCRIPTION,
        "about_text": ABOUT_TEXT,
    }


def get_about_html() -> str:
    """获取关于对话框的HTML内容"""
    return f"""
<h2>{APP_NAME}</h2>
<p><b>版本：</b>{DISPLAY_VERSION}</p>
<p><b>作者：</b>{AUTHOR}</p>
<p><strong>---------------------------------------------------</strong><br/><br/>{ABOUT_TEXT}<br/><br/><strong>---------------------------------------------------</strong></p>
<p><b>联系邮箱：</b>{AUTHOR_EMAIL}</p>
"""
