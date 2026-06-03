"""
GUI 服务层 — 可独立测试的业务逻辑模块。

与 gui/handlers 的区别：
- handlers 处理 GUI 事件流程（需要 QWidget 上下文）
- services 处理纯业务逻辑（输入普通值，输出普通值，无 Qt 依赖）
"""

from .config_marshaller import ConfigMarshaller
from .icon_auto_loader import IconAutoLoader
from .version_info_detector import VersionInfoDetector

__all__ = [
    "ConfigMarshaller",
    "IconAutoLoader",
    "VersionInfoDetector",
]
