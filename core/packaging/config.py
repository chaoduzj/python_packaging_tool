"""
打包配置数据类 — 类型化的打包参数，替代 Dict[str, Any] 在模块间传递。

定义单一、类型安全的配置结构，消除 key 拼写错误和散布多处的默认值。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class PackagingConfig:
    """打包配置的单一事实来源。

    所有打包模块通过此对象交换配置，替代原始的 Dict[str, Any]。
    默认值在此声明一次，不再分散在 MainWindow / Packager / NuitkaPackager 中。
    """

    # ---- 必填字段 ----
    script_path: str  # 主脚本路径

    # ---- 路径配置 ----
    project_dir: str = ""  # 项目根目录（自动从 script_path 推导）
    output_dir: Optional[str] = None  # 输出目录（None = 使用默认）
    icon_path: Optional[str] = None  # 图标路径
    program_name: Optional[str] = None  # 程序名称
    python_path: Optional[str] = None  # Python 解释器路径
    gcc_path: Optional[str] = None  # GCC 编译器路径

    # ---- 打包工具 ----
    tool: str = "nuitka"  # "nuitka" | "pyinstaller"

    # ---- 打包选项 ----
    onefile: bool = True  # 单文件模式
    console: bool = False  # 显示控制台（GUI 程序默认关闭）
    clean: bool = True  # 清理构建缓存
    upx: bool = False  # 启用 UPX 压缩
    use_venv: bool = True  # 使用虚拟环境
    lto: bool = True  # 启用 LTO 链接优化
    python_opt: bool = True  # 启用 Python 优化标志

    # ---- 模块控制 ----
    exclude_modules: List[str] = field(default_factory=list)

    # ---- 框架信息（由分析器填充） ----
    qt_framework: Optional[str] = None  # 主 Qt 框架名（如 "PyQt6"）
    detected_gui_frameworks: Set[str] = field(default_factory=set)
    uses_tkinter: bool = False
    uses_numpy: bool = False
    uses_matplotlib: bool = False

    # ---- 版本信息 ----
    version_info: Dict[str, Any] = field(default_factory=dict)
    version_file: Optional[str] = None  # 临时版本文件路径

    # ---- Nuitka 高级选项 ----
    nuitka_advanced_options: Dict[str, Any] = field(default_factory=dict)

    # ---- 额外数据文件 ----
    extra_data: List[str] = field(default_factory=list)

    # ---- 兼容性：支持旧的 config["key"] 访问方式 ----
    def as_dict(self) -> Dict[str, Any]:
        """转换为旧版 dict 格式（用于向后兼容）。"""
        return {
            "script_path": self.script_path,
            "project_dir": self.project_dir,
            "output_dir": self.output_dir,
            "icon_path": self.icon_path,
            "program_name": self.program_name,
            "python_path": self.python_path,
            "tool": self.tool,
            "gcc_path": self.gcc_path,
            "onefile": self.onefile,
            "console": self.console,
            "clean": self.clean,
            "upx": self.upx,
            "use_venv": self.use_venv,
            "lto": self.lto,
            "python_opt": self.python_opt,
            "exclude_modules": self.exclude_modules,
            "qt_framework": self.qt_framework,
            "detected_gui_frameworks": self.detected_gui_frameworks,
            "uses_tkinter": self.uses_tkinter,
            "uses_numpy": self.uses_numpy,
            "uses_matplotlib": self.uses_matplotlib,
            "version_info": self.version_info,
            "version_file": self.version_file,
            "nuitka_advanced_options": self.nuitka_advanced_options,
            "extra_data": self.extra_data,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PackagingConfig":
        """从旧版 dict 创建（向后兼容过渡期）。"""
        return cls(
            script_path=d.get("script_path", ""),
            project_dir=d.get("project_dir", ""),
            output_dir=d.get("output_dir"),
            icon_path=d.get("icon_path"),
            program_name=d.get("program_name"),
            python_path=d.get("python_path"),
            tool=d.get("tool", "nuitka"),
            gcc_path=d.get("gcc_path"),
            onefile=d.get("onefile", True),
            console=d.get("console", False),
            clean=d.get("clean", True),
            upx=d.get("upx", False),
            use_venv=d.get("use_venv", True),
            lto=d.get("lto", True),
            python_opt=d.get("python_opt", True),
            exclude_modules=d.get("exclude_modules", []),
            qt_framework=d.get("qt_framework"),
            detected_gui_frameworks=d.get("detected_gui_frameworks", set()),
            uses_tkinter=d.get("uses_tkinter", False),
            uses_numpy=d.get("uses_numpy", False),
            uses_matplotlib=d.get("uses_matplotlib", False),
            version_info=d.get("version_info", {}),
            version_file=d.get("version_file"),
            nuitka_advanced_options=d.get("nuitka_advanced_options", {}),
            extra_data=d.get("extra_data", []),
        )

    # ------------------------------------------------------------------
    # dict 兼容层（长期保留，非过渡期）
    # ------------------------------------------------------------------
    # 历史上内部代码使用 dict 传递配置，迁移到 dataclass 后为避免大规模
    # 重写（当前 7 个文件、26 处下标访问），保留以下 dunder 方法使
    # PackagingConfig 同时支持属性访问 (config.tool) 与下标访问
    # (config["tool"])。两套语法等价，调用方可自由选择。
    #
    # 这并非"待清理的过渡代码"，而是有意的双模 API：
    # - 属性访问：类型提示友好，IDE 补全完整
    # - 下标访问：与历史 dict 代码、JSON 序列化场景兼容
    # 删除前需先把全部 26 处下标访问改为属性访问。

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict.get() 调用方式。"""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """兼容 config["key"] 下标访问（与属性访问等价）。"""
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """兼容 config["key"] = value 下标赋值（与属性赋值等价）。"""
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        """兼容 "key" in config 成员检测。"""
        return hasattr(self, key)
