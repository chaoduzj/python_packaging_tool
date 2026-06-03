"""
Python打包工具 - 主窗口

本模块实现主应用程序窗口，遵循PyQt6最佳实践：
1. 关注点分离（UI、逻辑、样式）
2. 使用QThreadPool处理后台任务
3. 全面使用类型提示
4. 集中式主题管理
5. 模块化组件组织
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from typing import Dict, Optional

from PyQt6.QtCore import (
    QSettings,
    Qt,
    QThreadPool,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# 导入核心模块
from core.dependency_analyzer import DependencyAnalyzer
from core.packager import Packager
from core.packaging.config import PackagingConfig

# 导入重构后的GUI模块
from gui.controllers.workers import PackagingWorker
from gui.dialogs.nuitka_options_dialog import NuitkaOptionsDialog
from gui.services.config_marshaller import ConfigMarshaller
from gui.services.icon_auto_loader import IconAutoLoader
from gui.services.version_info_detector import VersionInfoDetector
from gui.styles.themes import (
    ThemeManager,
    ThemeMode,
)
from gui.widgets.icons import IconGenerator
from utils.constants import get_nuitka_containing_dir, is_bundled, is_nuitka_compiled
from utils.dependency_manager import DependencyManager
from utils.gcc_downloader import GCCDownloader, validate_mingw_directory

# 导入版本信息
from version import APP_NAME, AUTHOR_EMAIL, DISPLAY_VERSION, get_about_html


class MainWindow(QMainWindow):
    """
    主应用程序窗口 - PyQt6最佳实践实现

    主要改进：
    - 使用QThreadPool处理后台任务
    - 通过ThemeManager进行集中式主题管理
    - 通过IconGenerator分离图标生成
    - 清晰的信号/槽模式用于线程通信
    - 全面使用类型提示
    """

    # 用于线程安全通信的应用程序信号
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    update_exclude_modules_signal = pyqtSignal(str)
    update_download_progress_signal = pyqtSignal(str)
    gcc_download_complete_signal = pyqtSignal(str)  # GCC 下载完成，参数为路径
    gcc_download_reset_button_signal = pyqtSignal()  # 重置下载按钮
    analyze_finished_signal = pyqtSignal()  # 依赖分析完成

    def __init__(self) -> None:
        super().__init__()
        self.resize(900, 700)

        # 初始化核心组件
        self._init_directories()
        self._init_managers()
        self._init_state()
        self._init_ui()
        self._connect_signals()
        self._load_settings()
        self._apply_initial_theme()

        # 延迟检查打开次数，确保主窗口已经显示
        QTimer.singleShot(1000, self._check_launch_count_and_donate)

    def _init_directories(self) -> None:
        """初始化应用程序目录"""
        self.app_dir = self._get_app_dir()

        # Config directory - 始终使用用户目录，确保配置持久化（尤其是打包后的exe）
        # 这样GCC配置等可以在重启后保留
        user_config_dir = os.path.join(os.path.expanduser("~"), ".python_packaging_tool")
        try:
            os.makedirs(user_config_dir, exist_ok=True)
            config_dir = user_config_dir
        except Exception:
            config_dir = os.path.join(self.app_dir, "config")
            try:
                os.makedirs(config_dir, exist_ok=True)
            except Exception:
                pass

        self.config_dir = config_dir
        self.gcc_config_file = os.path.join(config_dir, "gcc_config.json")
        self.theme_config_file = os.path.join(config_dir, "theme_config.json")

    def _init_managers(self) -> None:
        """初始化管理器对象"""
        # 主题和图标管理
        self.icon_generator = IconGenerator(self.app_dir)
        self.theme_manager = ThemeManager(self.app_dir)

        # 生成主题图标
        self.icon_generator.generate_theme_icons()

        # 依赖管理
        self.dependency_manager = DependencyManager()

        # 服务层（可独立测试的业务逻辑）
        self.config_marshaller = ConfigMarshaller()
        self.version_detector = VersionInfoDetector()
        self.icon_loader = IconAutoLoader()

        # 用于后台任务的线程池
        self.thread_pool = QThreadPool.globalInstance()

    def _init_state(self) -> None:
        """初始化应用程序状态"""
        # 日志最大化状态
        self._log_maximized = False

        # GCC配置状态
        self.gcc_config_loaded = False
        self.gcc_config_loading = False

        # 下载状态
        self.is_downloading = False
        self.cancel_download = False
        self.download_thread: Optional[threading.Thread] = None

        # 打包状态
        self.is_packaging = False
        self.cancel_packaging = False
        self.packaging_process: Optional[subprocess.Popen] = None
        self._current_packaging_worker: Optional[PackagingWorker] = None

        # 跟踪之前的项目目录和脚本路径以进行变更检测
        self._previous_project_dir: Optional[str] = None
        self._previous_script_path: Optional[str] = None

        # 版权信息
        self.version_info = {
            "product_name": "",
            "company_name": "",
            "file_description": "",
            "copyright": "Copyright © 2026",
            "version": "1.0.0",
        }

        # 控制台自动管理（根据脚本自动判断）
        self._console_auto_managed = True

        # 图标手动选择标志（防止自动加载覆盖用户选择）
        self._icon_manually_set = False

        # Nuitka 高级选项（基于最佳实践）
        self.nuitka_advanced_options = {}

    def _connect_signals(self) -> None:
        """连接应用程序信号到槽"""
        self.log_signal.connect(self._on_log_message)
        self.finished_signal.connect(self._on_task_finished)
        self.update_exclude_modules_signal.connect(self._on_exclude_modules_update)
        self.update_download_progress_signal.connect(self._on_download_progress_update)
        self.gcc_download_complete_signal.connect(self._on_gcc_download_complete)
        self.gcc_download_reset_button_signal.connect(self._on_gcc_download_reset_button)
        self.analyze_finished_signal.connect(self._on_analyze_finished)

        # 主题改变信号
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

    def _load_settings(self) -> None:
        """加载保存的设置"""
        self._load_theme_setting()

        # 自动加载 GCC 配置（如果在 Nuitka 模式下）
        if hasattr(self, "nuitka_radio") and self.nuitka_radio.isChecked():
            self.load_gcc_config()

    def _apply_initial_theme(self) -> None:
        """应用初始主题"""
        self.apply_theme()
        self._update_theme_button_state()

    # =========================================================================
    # Directory and Resource Management
    # =========================================================================

    def _get_app_dir(self) -> str:
        """
        获取应用程序目录（兼容打包后的exe）。

        对于打包后的exe，使用临时目录以避免污染exe目录。
        """
        if is_bundled():
            app_temp_dir = os.path.join(tempfile.gettempdir(), "python_packaging_tool")
            try:
                os.makedirs(app_temp_dir, exist_ok=True)
                return app_temp_dir
            except Exception:
                return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(__file__))

    def _get_resource_path(self, relative_path: str) -> Optional[str]:
        """获取资源文件路径（兼容 PyInstaller 和 Nuitka 打包后的 exe）"""
        if is_bundled():
            possible_paths = []

            # Nuitka onefile 解包目录（优先）
            if is_nuitka_compiled():
                nuitka_dir = get_nuitka_containing_dir()
                if nuitka_dir:
                    possible_paths.append(os.path.join(nuitka_dir, relative_path))
                    if relative_path.endswith("icon.ico"):
                        possible_paths.append(os.path.join(nuitka_dir, "icon.ico"))

            # PyInstaller单文件模式使用_MEIPASS
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                possible_paths.append(os.path.join(meipass, relative_path))
                if relative_path.endswith("icon.ico"):
                    possible_paths.append(os.path.join(meipass, "icon.ico"))

            possible_paths.extend(
                [
                    os.path.join(os.path.dirname(sys.executable), relative_path),
                    os.path.join(os.path.dirname(sys.executable), "icon.ico")
                    if relative_path.endswith("icon.ico")
                    else None,
                    os.path.join(os.getcwd(), relative_path),
                    os.path.join(os.getcwd(), "icon.ico") if relative_path.endswith("icon.ico") else None,
                    relative_path,
                ]
            )

            # 过滤None值
            possible_paths = [p for p in possible_paths if p is not None]

            for path in possible_paths:
                if os.path.exists(path):
                    return path

            # 如果找不到文件，对于图标文件，尝试从exe资源中提取
            if relative_path.endswith("icon.ico") and sys.platform == "win32":
                # 返回exe路径，Qt会自动从exe资源中提取图标
                return sys.executable

            return None
        else:
            return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)

    # =========================================================================
    # UI Initialization
    # =========================================================================

    def _init_ui(self) -> None:
        """初始化用户界面"""
        # 创建菜单栏
        self._create_menu_bar()

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Build UI sections
        self._create_file_selection_group(main_layout)
        self._create_tool_selection_group(main_layout)
        self._create_options_group(main_layout)
        self._create_log_group(main_layout)
        self._create_button_bar(main_layout)

        # Set window icon
        self._set_window_icon()

        # Initial log message
        self.append_log("准备就绪...")

    def _create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar = self.menuBar()
        if menubar is None:
            return

        # ===== 文件菜单 =====
        file_menu = menubar.addMenu("文件")
        if file_menu is None:
            return

        # 主题切换子菜单
        theme_menu = QMenu("主题切换", self)

        self.theme_system_action = QAction("🖥️ 跟随系统", self)
        self.theme_system_action.setCheckable(True)
        self.theme_system_action.setChecked(True)
        self.theme_system_action.triggered.connect(lambda: self.set_theme(ThemeMode.SYSTEM))
        theme_menu.addAction(self.theme_system_action)

        self.theme_light_action = QAction("☀️ 浅色模式", self)
        self.theme_light_action.setCheckable(True)
        self.theme_light_action.triggered.connect(lambda: self.set_theme(ThemeMode.LIGHT))
        theme_menu.addAction(self.theme_light_action)

        self.theme_dark_action = QAction("🌙 深色模式", self)
        self.theme_dark_action.setCheckable(True)
        self.theme_dark_action.triggered.connect(lambda: self.set_theme(ThemeMode.DARK))
        theme_menu.addAction(self.theme_dark_action)

        file_menu.addMenu(theme_menu)
        file_menu.addSeparator()

        # 退出
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ===== 帮助菜单 =====
        help_menu = menubar.addMenu("帮助")
        if help_menu is None:
            return

        # 问题反馈
        feedback_action = QAction("问题反馈", self)
        feedback_action.triggered.connect(self._show_feedback_dialog)
        help_menu.addAction(feedback_action)

        # 文澜书库
        wklan_action = QAction("文澜书库", self)
        wklan_action.triggered.connect(lambda: webbrowser.open("https://books.wklan.com"))
        help_menu.addAction(wklan_action)

        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

        # ===== 捐赠菜单 =====
        donate_action = QAction("捐赠", self)
        donate_action.triggered.connect(self._show_donate_dialog)
        menubar.addAction(donate_action)

    def _show_feedback_dialog(self) -> None:
        """显示问题反馈对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("问题反馈")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)

        # 应用与主窗口一致的样式
        colors = self.theme_manager.colors
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
                color: {colors.text_primary};
            }}
            QLabel {{
                color: {colors.text_primary};
                background-color: transparent;
            }}
            QTextEdit {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                padding: 5px;
                color: {colors.text_primary};
            }}
            QPushButton {{
                background-color: {colors.accent_primary};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.accent_pressed};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # 软件信息（包含版本号）
        info_label = QLabel(f"<h3>{APP_NAME}</h3><p><b>软件版本：</b>{DISPLAY_VERSION}</p>")
        layout.addWidget(info_label)

        # 获取当前配置信息
        config = self.get_config()
        config_text = f"""
<b>当前打包配置：</b><br>
- 打包工具: {config.tool}<br>
- 单文件模式: {"是" if config.onefile else "否"}<br>
- 显示控制台: {"是" if config.console else "否"}<br>
- 清理构建缓存: {"是" if config.clean else "否"}<br>
- 使用UPX压缩: {"是" if config.upx else "否"}<br>
- 脚本路径: {config.script_path or "N/A"}<br>
- 项目目录: {config.project_dir or "N/A"}<br>
- 输出目录: {config.output_dir or "N/A"}<br>
"""
        config_label = QLabel(config_text)
        config_label.setWordWrap(True)
        layout.addWidget(config_label)

        # 日志信息
        log_label = QLabel("<b>日志输出：</b>")
        layout.addWidget(log_label)

        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setPlainText(self.log_text.toPlainText())
        log_text.setMaximumHeight(200)
        layout.addWidget(log_text)

        # 专属特权说明
        highlight_color = "#FFD700" if self.theme_manager.is_dark else "#FF0000"
        vip_label = QLabel(
            f"<br><span style='color: {highlight_color};'>捐赠用户在遇到打包问题时，将<b>优先获得技术支持和问题排查协助</b>。</span><br>"
        )
        layout.addWidget(vip_label)

        # 作者邮箱
        email_label = QLabel(f"<b>作者邮箱：</b> {AUTHOR_EMAIL}")
        email_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        email_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def show_email_context_menu(pos):
            """显示邮箱的中文右键菜单"""
            context_menu = QMenu(email_label)

            # 设置菜单样式
            context_menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {colors.background_secondary};
                    border: 1px solid {colors.border_primary};
                    color: {colors.text_primary};
                }}
                QMenu::item {{
                    padding: 5px 20px;
                    background-color: {colors.background_secondary};
                    color: {colors.text_primary};
                }}
                QMenu::item:selected {{
                    background-color: {colors.accent_primary};
                    color: white;
                }}
            """)

            # 复制动作
            copy_action = QAction("复制", email_label)
            copy_action.triggered.connect(lambda: self._copy_selected_text(email_label))
            context_menu.addAction(copy_action)

            context_menu.exec(email_label.mapToGlobal(pos))

        email_label.customContextMenuRequested.connect(show_email_context_menu)
        layout.addWidget(email_label)

        # 提示信息
        tip_label = QLabel("<br><i>请将以上信息复制后发送到邮箱，以便我们更好地帮助您解决问题。</i>")
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        # 按钮区
        btn_layout = QHBoxLayout()

        # 一键复制按钮
        copy_btn = QPushButton("一键复制")

        def copy_all():
            full_text = f"""{APP_NAME} - 问题反馈
软件版本：{DISPLAY_VERSION}

当前打包配置：
- 打包工具: {config.get("tool", "N/A")}
- 单文件模式: {"是" if config.get("onefile") else "否"}
- 显示控制台: {"是" if config.get("console") else "否"}
- 清理构建缓存: {"是" if config.get("clean") else "否"}
- 使用UPX压缩: {"是" if config.get("upx") else "否"}
- 脚本路径: {config.get("script_path") or "N/A"}
- 项目目录: {config.get("project_dir") or "N/A"}
- 输出目录: {config.get("output_dir") or "N/A"}

日志输出：
{self.log_text.toPlainText()}
"""
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(full_text)
                QMessageBox.information(dialog, "提示", "已复制到剪贴板！")

        copy_btn.setProperty("buttonType", "primary")
        copy_btn.clicked.connect(copy_all)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        dialog.exec()

    def _copy_selected_text(self, label: QLabel) -> None:
        """复制标签中选中的文本到剪贴板"""
        selected_text = label.selectedText()
        if selected_text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(selected_text)

    def _show_donate_dialog(self) -> None:
        """显示捐赠对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("☕ 请作者喝杯咖啡")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(450)

        # 应用与主窗口一致的样式
        colors = self.theme_manager.colors
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
            }}
            QLabel {{
                color: {colors.text_primary};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        # 感谢语和特权说明
        highlight_color = "#FFD700" if self.theme_manager.is_dark else "#FF0000"
        desc_label = QLabel(
            "感谢您的支持！您的捐赠是我们持续维护和优化的最大动力。<br><br>"
            "<b>💡 专属福利：</b><br>"
            f"<span style='color: {highlight_color};'>捐赠用户在遇到打包问题时，将<b>优先获得技术支持和问题排查协助</b>。</span><br>"
            "（在反馈问题时，请附带您的捐赠截图或备注信息哦）"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 14px; line-height: 1.5;")
        layout.addWidget(desc_label)

        # 二维码区域
        qr_layout = QHBoxLayout()
        qr_layout.setSpacing(40)

        def create_qr_widget(img_name: str, title: str) -> QWidget:
            widget = QWidget()
            v_layout = QVBoxLayout(widget)
            v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_layout.setContentsMargins(0, 0, 0, 0)

            # 图片
            img_label = QLabel()
            img_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", img_name)
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                scaled_pixmap = pixmap.scaled(
                    220,
                    300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_label.setPixmap(scaled_pixmap)
            else:
                img_label.setText(f"[缺少图片文件: {img_name}]")

            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_layout.addWidget(img_label)

            # 标题
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 5px;")
            v_layout.addWidget(title_label)

            return widget

        # 支付宝
        alipay_widget = create_qr_widget("alipay.jpg", "支付宝")
        qr_layout.addWidget(alipay_widget)

        # 微信
        wechat_widget = create_qr_widget("wechat_pay.png", "微信支付")
        qr_layout.addWidget(wechat_widget)

        layout.addLayout(qr_layout)

        # 底部关闭按钮（前3秒禁用，防止误关）
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("感谢支持 (3s)")
        close_btn.setMinimumWidth(120)
        close_btn.setMinimumHeight(35)
        close_btn.setProperty("buttonType", "primary")
        close_btn.setEnabled(False)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # 3 秒倒计时，逐步启用关闭按钮
        self._countdown = 3

        def tick():
            self._countdown -= 1
            if self._countdown > 0:
                close_btn.setText(f"感谢支持 ({self._countdown}s)")
            else:
                close_btn.setText("感谢支持")
                close_btn.setEnabled(True)
                timer.stop()

        timer = QTimer(dialog)
        timer.timeout.connect(tick)
        timer.start(1000)

        dialog.exec()

    def _check_launch_count_and_donate(self) -> None:
        """检查软件打开次数并根据规则弹出捐赠框"""
        settings = QSettings("PythonPackagingTool", "LaunchCount")
        count = settings.value("count", 0, type=int)

        count += 1
        settings.setValue("count", count)

        # 目标次数：5, 10, 20, 30, 40...
        target_counts = [5, 10]
        if count > 10 and count % 10 == 0:
            target_counts.append(count)

        if count in target_counts:
            self._show_donate_dialog()

    def _show_about_dialog(self) -> None:
        """显示关于对话框（支持文本复制）"""
        dialog = QDialog(self)
        dialog.setWindowTitle("关于")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(350)

        # 设置对话框图标（与主窗口一致）
        dialog.setWindowIcon(self.windowIcon())

        # 应用与主窗口一致的样式
        colors = self.theme_manager.colors
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
                color: {colors.text_primary};
            }}
            QLabel {{
                color: {colors.text_primary};
                background-color: transparent;
            }}
            QTextBrowser {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                padding: 10px;
                color: {colors.text_primary};
            }}
            QPushButton {{
                background-color: {colors.accent_primary};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.accent_pressed};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # 顶部图标和标题区域
        top_layout = QHBoxLayout()

        # 添加应用图标
        icon_label = QLabel()
        icon_pixmap = self.windowIcon().pixmap(64, 64)  # 64x64 图标
        if not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(icon_label)

        top_layout.addSpacing(10)

        # 使用 QTextBrowser 显示内容，支持选择和复制
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(False)
        text_browser.setHtml(get_about_html())
        text_browser.setMinimumHeight(150)
        top_layout.addWidget(text_browser)

        layout.addLayout(top_layout)

        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        dialog.exec()

    def _create_file_selection_group(self, parent_layout: QVBoxLayout) -> None:
        """创建文件选择组"""
        self.file_group = file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)

        # Project directory
        project_layout = QHBoxLayout()
        project_layout.addWidget(QLabel("项目目录:"))
        self.project_dir_edit = QLineEdit()
        self.project_dir_edit.setPlaceholderText("可选，选择Python项目根目录")
        self.project_dir_edit.textChanged.connect(self.on_project_dir_changed)
        project_layout.addWidget(self.project_dir_edit)
        project_btn = QPushButton("浏览")
        project_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        project_btn.clicked.connect(self.browse_project_dir)
        project_layout.addWidget(project_btn)
        file_layout.addLayout(project_layout)

        # 运行脚本
        script_layout = QHBoxLayout()
        script_layout.addWidget(QLabel("运行脚本:"))
        self.script_path_edit = QLineEdit()
        self.script_path_edit.setPlaceholderText("必选，指定要执行的Python脚本")
        self.script_path_edit.textChanged.connect(self.on_script_path_changed)
        script_layout.addWidget(self.script_path_edit)
        script_btn = QPushButton("浏览")
        script_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        script_btn.clicked.connect(self.browse_script)
        script_layout.addWidget(script_btn)
        file_layout.addLayout(script_layout)

        # 输出目录
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("可选，默认为项目目录下的build文件夹")
        output_layout.addWidget(self.output_dir_edit)
        output_btn = QPushButton("浏览")
        output_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        output_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(output_btn)
        file_layout.addLayout(output_layout)

        # 图标路径
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel("程序图标:"))
        self.icon_path_edit = QLineEdit()
        self.icon_path_edit.setPlaceholderText("可选，支持 .ico/.png/.svg 等格式，自动转换为多尺寸图标")
        icon_layout.addWidget(self.icon_path_edit)
        icon_btn = QPushButton("浏览")
        icon_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        icon_btn.clicked.connect(self.browse_icon)
        icon_layout.addWidget(icon_btn)
        file_layout.addLayout(icon_layout)

        # 程序名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("程序名称:"))
        self.program_name_edit = QLineEdit()
        self.program_name_edit.setPlaceholderText("可选，指定打包后的exe文件名（不含.exe扩展名）")
        name_layout.addWidget(self.program_name_edit)
        file_layout.addLayout(name_layout)

        # Python路径
        python_layout = QHBoxLayout()
        python_layout.addWidget(QLabel("Python路径:"))
        self.python_path_edit = QLineEdit()
        self.python_path_edit.setPlaceholderText("可选，留空将自动检测系统Python")
        python_layout.addWidget(self.python_path_edit)
        python_btn = QPushButton("浏览")
        python_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        python_btn.clicked.connect(self.browse_python)
        python_layout.addWidget(python_btn)
        file_layout.addLayout(python_layout)

        parent_layout.addWidget(file_group)

    def _create_tool_selection_group(self, parent_layout: QVBoxLayout) -> None:
        """创建工具选择组"""
        self.tool_group = tool_group = QGroupBox("打包工具")
        tool_layout = QVBoxLayout(tool_group)

        tool_radio_layout = QHBoxLayout()
        self.nuitka_radio = QRadioButton("Nuitka")
        self.nuitka_radio.setChecked(True)
        self.nuitka_radio.toggled.connect(self.on_tool_changed)

        self.pyinstaller_radio = QRadioButton("PyInstaller")
        self.pyinstaller_radio.toggled.connect(self.on_tool_changed)

        tool_radio_layout.addWidget(self.nuitka_radio)
        tool_radio_layout.addWidget(self.pyinstaller_radio)
        tool_radio_layout.addStretch()
        tool_layout.addLayout(tool_radio_layout)

        # GCC path widget (Nuitka only)
        self.gcc_widget = QWidget()
        gcc_widget_layout = QVBoxLayout(self.gcc_widget)
        gcc_widget_layout.setContentsMargins(0, 0, 0, 0)
        gcc_widget_layout.setSpacing(5)

        gcc_layout = QHBoxLayout()
        gcc_layout.addWidget(QLabel("GCC编译链:"))
        self.gcc_path_edit = QLineEdit()
        self.gcc_path_edit.setPlaceholderText("必选，指定GCC工具链目录，一般为mingw64或mingw32目录")
        self.gcc_path_edit.textChanged.connect(self.on_gcc_path_changed)
        gcc_layout.addWidget(self.gcc_path_edit)
        self.gcc_browse_btn = QPushButton("浏览")
        self.gcc_browse_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        self.gcc_browse_btn.clicked.connect(self.browse_gcc)
        gcc_layout.addWidget(self.gcc_browse_btn)
        self.gcc_download_btn = QPushButton("自动下载")
        self.gcc_download_btn.clicked.connect(self.download_gcc)
        gcc_layout.addWidget(self.gcc_download_btn)

        # Nuitka 高级选项按钮
        self.nuitka_options_btn = QPushButton("高级选项")
        self.nuitka_options_btn.setToolTip("配置 Nuitka 高级选项（基于官方最佳实践）")
        self.nuitka_options_btn.clicked.connect(self._show_nuitka_options_dialog)
        gcc_layout.addWidget(self.nuitka_options_btn)

        gcc_widget_layout.addLayout(gcc_layout)

        # GCC download progress label
        self.gcc_download_label = QLabel("")
        gcc_widget_layout.addWidget(self.gcc_download_label)

        tool_layout.addWidget(self.gcc_widget)
        self.gcc_widget.setVisible(self.nuitka_radio.isChecked())

        parent_layout.addWidget(tool_group)

    def _create_options_group(self, parent_layout: QVBoxLayout) -> None:
        """Create packaging options group"""
        self.options_group = options_group = QGroupBox("打包选项")
        options_layout = QVBoxLayout(options_group)

        # 复选框行
        checkboxes_layout = QHBoxLayout()

        self.onefile_check = QCheckBox("单文件模式")
        self.onefile_check.setChecked(True)
        self.onefile_check.setToolTip("打包成单个exe文件")

        self.clean_check = QCheckBox("清理构建缓存")
        self.clean_check.setChecked(True)
        self.clean_check.setToolTip("打包前清理临时文件")

        self.venv_check = QCheckBox("使用虚拟环境")
        self.venv_check.setChecked(True)
        self.venv_check.setToolTip("在虚拟环境中打包以隔离依赖")

        self.upx_check = QCheckBox("使用UPX压缩")
        self.upx_check.setChecked(True)  # Nuitka 默认开启 UPX
        self.upx_check.setToolTip("压缩exe体积（需安装UPX）")
        # 初始可见性根据工具选择决定
        if hasattr(self, "nuitka_radio"):
            is_nuitka = self.nuitka_radio.isChecked()
            self.upx_check.setVisible(is_nuitka)
            if not is_nuitka:
                self.upx_check.setChecked(False)

        self.console_check = QCheckBox("显示控制台窗口")
        self.console_check.setChecked(False)
        self.console_check.setToolTip("运行时是否显示CMD窗口")
        self.console_check.stateChanged.connect(self._on_console_check_changed)

        self.version_info_check = QCheckBox("添加版权信息")
        self.version_info_check.setChecked(False)
        self.version_info_check.setToolTip("配置软件版权、公司等信息")
        self.version_info_check.clicked.connect(self._on_version_info_check_clicked)

        checkboxes_layout.addWidget(self.onefile_check)
        checkboxes_layout.addWidget(self.clean_check)
        checkboxes_layout.addWidget(self.venv_check)
        checkboxes_layout.addWidget(self.upx_check)
        checkboxes_layout.addWidget(self.console_check)
        checkboxes_layout.addWidget(self.version_info_check)
        checkboxes_layout.addStretch()

        options_layout.addLayout(checkboxes_layout)

        # Exclude modules row
        exclude_layout = QHBoxLayout()
        exclude_layout.addWidget(QLabel("排除模块:"))
        self.exclude_modules_edit = QLineEdit()
        self.exclude_modules_edit.setPlaceholderText(
            "可选，默认会自动排除，你也可以手动追加需要排除的模块，多个模块用逗号分隔，如：wx,wxPython,ui"
        )
        exclude_layout.addWidget(self.exclude_modules_edit)

        self.analyze_btn = QPushButton("分析依赖")
        self.analyze_btn.setMinimumHeight(35)
        self.analyze_btn.setStyleSheet("QPushButton { min-width: 0; }")  # 覆盖全局样式，让按钮宽度适应文字
        self.analyze_btn.clicked.connect(self.analyze_dependencies)
        exclude_layout.addWidget(self.analyze_btn)

        options_layout.addLayout(exclude_layout)

        parent_layout.addWidget(options_group)

    def _create_log_group(self, parent_layout: QVBoxLayout) -> None:
        """创建日志输出组"""
        self.log_group = log_group = QGroupBox("日志输出")
        log_layout = QVBoxLayout(log_group)

        # 日志区域顶部工具栏（放置最大化按钮和复制日志按钮）
        log_toolbar = QHBoxLayout()
        log_toolbar.setContentsMargins(0, 0, 0, 0)

        # 一键复制完整日志按钮
        self.log_copy_btn = QPushButton("一键复制完整日志")
        self.log_copy_btn.setFixedHeight(24)
        self.log_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_copy_btn.setToolTip("复制所有日志内容到剪贴板")
        self.log_copy_btn.setStyleSheet("QPushButton {  padding: 0px 8px;  font-size: 12px;}")
        self.log_copy_btn.clicked.connect(self._copy_all_log)
        log_toolbar.addWidget(self.log_copy_btn)

        log_toolbar.addStretch()

        self.log_maximize_btn = QPushButton()
        self.log_maximize_btn.setFixedSize(22, 22)
        self.log_maximize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_maximize_btn.setToolTip("最大化日志")
        self.log_maximize_btn.clicked.connect(self._toggle_log_maximize)
        self._update_log_maximize_btn_icon()
        log_toolbar.addWidget(self.log_maximize_btn)

        log_layout.addLayout(log_toolbar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        parent_layout.addWidget(log_group)

    def _create_button_bar(self, parent_layout: QVBoxLayout) -> None:
        """Create bottom button bar"""
        self.btn_bar_widget = QWidget()
        btn_layout = QHBoxLayout(self.btn_bar_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        # 问题反馈文字链接（左侧）
        colors = self.theme_manager.colors
        self.feedback_label = QLabel(
            f'<a href="#" style="text-decoration: none; color: {colors.text_primary};">问题反馈</a>'
        )
        self.feedback_label.setOpenExternalLinks(False)
        self.feedback_label.linkActivated.connect(lambda: self._show_feedback_dialog())
        self.feedback_label.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self.feedback_label)

        # 间距
        btn_layout.addSpacing(15)

        # 请喝咖啡文字链接
        self.donate_label = QLabel(
            f'<a href="#" style="text-decoration: none; color: {colors.text_primary};">☕ 请作者喝杯咖啡</a>'
        )
        self.donate_label.setOpenExternalLinks(False)
        self.donate_label.linkActivated.connect(lambda: self._show_donate_dialog())
        self.donate_label.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self.donate_label)

        btn_layout.addStretch()

        # Action buttons
        self.package_btn = QPushButton("开始打包")
        self.package_btn.setMinimumHeight(40)
        self.package_btn.setMinimumWidth(120)
        self.package_btn.setProperty("buttonType", "primary")
        self.package_btn.clicked.connect(self.toggle_packaging)

        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setMinimumWidth(120)
        self.clear_btn.clicked.connect(self.clear_log)
        # 设置清空日志按钮为灰色背景
        self.clear_btn.setProperty("buttonType", "secondary")

        # 先添加清空日志按钮，再添加开始打包按钮
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.package_btn)

        parent_layout.addWidget(self.btn_bar_widget)

    def _on_version_info_check_clicked(self, checked: bool) -> None:
        """版权信息复选框被点击时触发（使用 clicked 信号更可靠）"""
        if checked:
            # 显示对话框
            self._show_version_info_dialog()

    def _detect_version_info_from_project(self) -> Dict[str, str]:
        """从项目目录检测版本信息（委托给 VersionInfoDetector）"""
        project_dir = self.project_dir_edit.text().strip() if hasattr(self, "project_dir_edit") else ""
        script_path = self.script_path_edit.text().strip() if hasattr(self, "script_path_edit") else ""
        return self.version_detector.detect(project_dir, script_path)

    def _show_version_info_dialog(self) -> None:
        """显示版权信息配置对话框"""
        # 尝试从项目目录检测版本信息
        detected_info = self._detect_version_info_from_project()

        # 检查是否为 Nuitka 打包（影响是否使用中文）
        is_nuitka = self.nuitka_radio.isChecked()

        # 检测 Windows SDK 支持（用于 Nuitka 中文版本信息）
        sdk_supported = False
        sdk_message = ""
        if is_nuitka:
            from core.packager import Packager

            temp_packager = Packager()
            sdk_supported, sdk_message = temp_packager.check_windows_sdk_support()

        # 合并检测到的信息和现有信息
        # 优先使用检测到的值，直接覆盖现有值

        # 产品名称：优先使用 APP_NAME，不存在则使用 APP_NAME_EN
        if detected_info.get("product_name"):
            self.version_info["product_name"] = detected_info["product_name"]
        elif detected_info.get("product_name_en"):
            self.version_info["product_name"] = detected_info["product_name_en"]

        # 文件描述：优先使用 DESCRIPTION，不存在则使用 DESCRIPTION_EN
        if detected_info.get("file_description"):
            self.version_info["file_description"] = detected_info["file_description"]
        elif detected_info.get("file_description_en"):
            self.version_info["file_description"] = detected_info["file_description_en"]

        # 版权信息：直接使用检测到的值（如果存在）
        if detected_info.get("copyright"):
            self.version_info["copyright"] = detected_info["copyright"]

        # 版本号：直接使用检测到的值（如果存在）
        if detected_info.get("version"):
            self.version_info["version"] = detected_info["version"]

        dialog = QDialog(self)
        dialog.setWindowTitle("添加版权信息")
        dialog.setMinimumWidth(450)

        # 设置对话框标志，确保不会影响父窗口
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # 应用与主窗口一致的样式
        colors = self.theme_manager.colors
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
                color: {colors.text_primary};
            }}
            QLabel {{
                color: {colors.text_primary};
                background-color: transparent;
            }}
            QLineEdit {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                padding: 5px;
                color: {colors.text_primary};
            }}
            QLineEdit:focus {{
                border: 1px solid {colors.accent_primary};
            }}
            QPushButton {{
                background-color: {colors.accent_primary};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.accent_pressed};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # 检查是否为Nuitka打包方式，如果是则显示提示
        if is_nuitka:
            if sdk_supported:
                # 检测到 Windows SDK，支持中文
                tip_label = QLabel(f"""
<b>✓ 支持中文版本信息</b><br>
{sdk_message}<br>
<span style="color: {colors.success};">您可以填写中文信息，系统将自动处理。</span>
                """)
                tip_label.setWordWrap(True)
                tip_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: {colors.background_secondary};
                        border: 1px solid {colors.success};
                        border-radius: 5px;
                        padding: 10px;
                        color: {colors.text_primary};
                    }}
                """)
            else:
                # 未检测到 Windows SDK，建议使用英文
                tip_label = QLabel(f"""
<b>提示：</b><br>当前Nuitka打包默认请填写英文信息。<br>
{sdk_message}<br><br>
如需支持中文信息，请先安装以下任一组件：<br>
• <b>Windows SDK</b> (推荐)<br>
• <b>Visual Studio Build Tools</b><br>
• <b>Visual Studio</b> (任意版本)
                """)
                tip_label.setWordWrap(True)
                tip_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: {colors.background_secondary};
                        border: 1px solid {colors.border_primary};
                        border-radius: 5px;
                        padding: 10px;
                        color: {colors.text_primary};
                    }}
                """)
            layout.addWidget(tip_label)
            layout.addSpacing(10)

        # 显示检测到版本信息的提示
        if any(detected_info.values()):
            # 重新检测以确定实际找到的文件路径
            project_dir = self.project_dir_edit.text().strip() if hasattr(self, "project_dir_edit") else ""
            script_path = self.script_path_edit.text().strip() if hasattr(self, "script_path_edit") else ""

            source_text = ""
            found_file = None

            # 查找实际使用的文件路径
            if project_dir and os.path.isdir(project_dir):
                # 先检查根目录
                for vf in ["version.py", "main.py"]:
                    vf_path = os.path.join(project_dir, vf)
                    if os.path.exists(vf_path):
                        found_file = vf_path
                        break

                # 如果根目录没找到，查找子目录
                if not found_file:
                    from utils.constants import SKIP_DIRECTORIES

                    skip_dirs = set(SKIP_DIRECTORIES) | {".tox", ".pytest_cache", "egg-info", ".eggs"}

                    priority_dirs = ["core", "src", "lib", "utils", "config"]

                    # 先查找常见子目录
                    for priority_dir in priority_dirs:
                        for vf in ["version.py", "main.py"]:
                            vf_path = os.path.join(project_dir, priority_dir, vf)
                            if os.path.exists(vf_path):
                                found_file = vf_path
                                break
                        if found_file:
                            break

                    # 如果优先目录没找到，递归查找
                    if not found_file:
                        for root, dirs, files in os.walk(project_dir):
                            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
                            for vf in ["version.py", "main.py"]:
                                if vf in files:
                                    found_file = os.path.join(root, vf)
                                    break
                            if found_file:
                                break

            # 如果还是没找到，使用脚本文件
            if not found_file and script_path and os.path.isfile(script_path):
                if script_path.lower().endswith((".py", ".pyw")):
                    found_file = script_path

            # 生成提示文本
            if found_file:
                # 计算相对路径用于显示
                if project_dir and found_file.startswith(project_dir):
                    rel_path = os.path.relpath(found_file, project_dir)
                    source_text = f"项目 {rel_path}"
                else:
                    source_text = f"文件 {os.path.basename(found_file)}"

            if source_text:
                detect_tip = QLabel(f"✓ 已从 {source_text} 中检测到版本信息")
            else:
                detect_tip = QLabel("✓ 已检测到版本信息")
            detect_tip.setStyleSheet(f"color: {colors.success}; font-size: 12px;")
            layout.addWidget(detect_tip)
            layout.addSpacing(5)

        # 表单布局
        form_layout = QFormLayout()

        # 产品名称
        self.version_product_name_edit = QLineEdit()
        self.version_product_name_edit.setText(self.version_info.get("product_name", ""))
        self.version_product_name_edit.setPlaceholderText("eg. My Application")
        form_layout.addRow("产品名称:", self.version_product_name_edit)

        # 公司名称
        self.version_company_name_edit = QLineEdit()
        self.version_company_name_edit.setText(self.version_info.get("company_name", ""))
        self.version_company_name_edit.setPlaceholderText("eg. XXX Tech Co., Ltd.")
        form_layout.addRow("公司名称:", self.version_company_name_edit)

        # 文件描述
        self.version_file_desc_edit = QLineEdit()
        self.version_file_desc_edit.setText(self.version_info.get("file_description", ""))
        self.version_file_desc_edit.setPlaceholderText("eg. This is a useful tool")
        form_layout.addRow("文件描述:", self.version_file_desc_edit)

        # 版权信息
        self.version_copyright_edit = QLineEdit()
        self.version_copyright_edit.setText(self.version_info.get("copyright", "Copyright © 2026"))
        self.version_copyright_edit.setPlaceholderText("eg. Copyright © 2024 XXX Company")
        form_layout.addRow("版权信息:", self.version_copyright_edit)

        # 版本号
        self.version_version_edit = QLineEdit()
        self.version_version_edit.setText(self.version_info.get("version", "1.0.0"))
        self.version_version_edit.setPlaceholderText("eg. 1.0.0")
        form_layout.addRow("版本号:", self.version_version_edit)

        layout.addLayout(form_layout)

        # 按钮（使用中文按钮）
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("确定")
        ok_btn.setProperty("buttonType", "primary")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.background_tertiary};
                color: {colors.text_primary};
                border: 1px solid {colors.border_primary};
            }}
            QPushButton:hover {{
                background-color: {colors.border_secondary};
            }}
        """)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # 显示对话框并处理结果
        result = dialog.exec()

        # 处理对话框结果
        if result == QDialog.DialogCode.Accepted:
            # 保存版权信息
            self.version_info = {
                "product_name": self.version_product_name_edit.text().strip(),
                "company_name": self.version_company_name_edit.text().strip(),
                "file_description": self.version_file_desc_edit.text().strip(),
                "copyright": self.version_copyright_edit.text().strip(),
                "version": self.version_version_edit.text().strip() or "1.0.0",
            }
            self.append_log(f"已配置版权信息: {self.version_info.get('product_name', 'N/A')}")
        else:
            # 用户取消，直接取消勾选
            # clicked 信号只在用户点击时触发，setChecked 不会触发，所以无需 blockSignals
            self.version_info_check.setChecked(False)

    def _set_window_icon(self) -> None:
        """设置窗口图标（兼容 PyInstaller 和 Nuitka 打包后的 exe）"""
        try:
            icon_filename = "icon.ico"
            possible_paths = []

            if is_bundled():
                # Nuitka onefile 解包目录（优先）
                if is_nuitka_compiled():
                    nuitka_dir = get_nuitka_containing_dir()
                    if nuitka_dir:
                        possible_paths.extend(
                            [
                                os.path.join(nuitka_dir, icon_filename),
                                os.path.join(nuitka_dir, "resources", "icons", icon_filename),
                            ]
                        )

                # PyInstaller的_MEIPASS
                meipass = getattr(sys, "_MEIPASS", None)
                if meipass:
                    possible_paths.extend(
                        [
                            os.path.join(meipass, icon_filename),
                            os.path.join(meipass, "resources", "icons", icon_filename),
                        ]
                    )

                # exe目录和当前工作目录
                exe_dir = os.path.dirname(sys.executable)
                possible_paths.extend(
                    [
                        os.path.join(exe_dir, icon_filename),
                        os.path.join(exe_dir, "resources", "icons", icon_filename),
                        os.path.join(os.getcwd(), icon_filename),
                    ]
                )

                for path in possible_paths:
                    if os.path.exists(path):
                        self.setWindowIcon(QIcon(path))
                        return
            else:
                # 开发模式
                icon_path = self._get_resource_path("resources/icons/icon.ico")
                if icon_path and os.path.exists(icon_path):
                    self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"加载图标失败: {e}")

    # =========================================================================
    # Theme Management
    # =========================================================================

    def set_theme(self, mode: ThemeMode) -> None:
        """设置主题模式"""
        self.theme_manager.current_mode = mode
        self._update_theme_button_state()
        self._save_theme_setting()
        self.apply_theme()

    def apply_theme(self) -> None:
        """将当前主题应用到界面"""
        app = QApplication.instance()
        if not app:
            return

        is_dark = self.theme_manager.is_dark

        # 根据主题获取图标路径（从resources/icons目录）
        if is_dark:
            check_icon = self.icon_generator.get_icon_path("resources/icons/check_dark.png")
            radio_icon = self.icon_generator.get_icon_path("resources/icons/radio_dark.png")
        else:
            check_icon = self.icon_generator.get_icon_path("resources/icons/check_light.png")
            radio_icon = self.icon_generator.get_icon_path("resources/icons/radio_light.png")

        # 应用样式表
        stylesheet = self.theme_manager.get_stylesheet(check_icon, radio_icon)
        self.setStyleSheet(stylesheet)

        # 更新GCC下载标签颜色
        if hasattr(self, "gcc_download_label"):
            color = self.theme_manager.get_label_color("warning" if is_dark else "accent")
            self.gcc_download_label.setStyleSheet(f"color: {color};")

        # 更新问题反馈文字颜色
        if hasattr(self, "feedback_label"):
            colors = self.theme_manager.colors
            self.feedback_label.setText(
                f'<a href="#" style="text-decoration: none; color: {colors.text_primary};">问题反馈</a>'
            )

        # 更新捐赠文字颜色
        if hasattr(self, "donate_label"):
            colors = self.theme_manager.colors
            self.donate_label.setText(
                f'<a href="#" style="text-decoration: none; color: {colors.text_primary};">☕ 请作者喝杯咖啡</a>'
            )

        # 更新日志最大化按钮图标（跟随主题颜色）
        if hasattr(self, "log_maximize_btn"):
            self._update_log_maximize_btn_icon()

    def _update_theme_button_state(self) -> None:
        """更新主题菜单状态以反映当前设置"""
        mode = self.theme_manager.current_mode

        self.theme_system_action.setChecked(mode == ThemeMode.SYSTEM)
        self.theme_light_action.setChecked(mode == ThemeMode.LIGHT)
        self.theme_dark_action.setChecked(mode == ThemeMode.DARK)

    def _load_theme_setting(self) -> None:
        """从配置文件加载主题设置"""
        try:
            if os.path.exists(self.theme_config_file):
                with open(self.theme_config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    mode_str = config.get("theme_mode", "system")
                    mode_map = {
                        "system": ThemeMode.SYSTEM,
                        "light": ThemeMode.LIGHT,
                        "dark": ThemeMode.DARK,
                    }
                    self.theme_manager.current_mode = mode_map.get(mode_str, ThemeMode.SYSTEM)
        except Exception as e:
            print(f"加载主题设置失败: {e}")

    def _save_theme_setting(self) -> None:
        """保存主题设置到配置文件"""
        try:
            config = {"theme_mode": self.theme_manager.current_mode.value}
            with open(self.theme_config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存主题设置失败: {e}")

    @pyqtSlot(bool)
    def _on_theme_changed(self, is_dark: bool) -> None:
        """处理主题改变信号"""
        self.apply_theme()

    # =========================================================================
    # 信号槽
    # =========================================================================

    @pyqtSlot(str)
    def _on_log_message(self, message: str) -> None:
        """处理日志消息信号"""
        self.append_log(message)

    @pyqtSlot(bool, str)
    def _on_task_finished(self, success: bool, message: str) -> None:
        """处理任务完成信号"""
        self.on_packaging_finished(success, message)

    @pyqtSlot(str)
    def _on_exclude_modules_update(self, modules: str) -> None:
        """处理排除模块更新信号"""
        self.update_exclude_modules_ui(modules)

    @pyqtSlot(str)
    def _on_download_progress_update(self, progress: str) -> None:
        """处理下载进度更新信号"""
        self.update_download_progress_ui(progress)

    # =========================================================================
    # 文件浏览方法
    # =========================================================================

    def browse_project_dir(self) -> None:
        """浏览项目目录"""
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.project_dir_edit.setText(os.path.normpath(path))

    def browse_script(self) -> None:
        """浏览脚本文件"""
        path, _ = QFileDialog.getOpenFileName(self, "选择运行脚本", "", "Python Files (*.py);;All Files (*)")
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.script_path_edit.setText(os.path.normpath(path))

    def browse_output_dir(self) -> None:
        """浏览输出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            normalized_path = os.path.normpath(path)

            # 安全检查：阻止用户选择受保护的系统目录作为输出目录
            from core.packager import Packager

            is_protected, matched_dir = Packager._is_protected_dir(normalized_path)
            if is_protected:
                self._show_warning(
                    "目录不安全",
                    f"您选择的目录是受保护的系统目录：\n\n"
                    f"{matched_dir}\n\n"
                    f"选择该目录作为输出目录将导致其中所有文件被清空！\n"
                    f"请选择项目子目录或专门的构建输出目录。",
                )
                return

            # 规范化路径，统一使用系统默认的路径分隔符
            self.output_dir_edit.setText(normalized_path)

    def browse_icon(self) -> None:
        """浏览图标文件"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择程序图标",
            "",
            "Icon Files (*.ico *.png *.svg *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.icon_path_edit.setText(os.path.normpath(path))

    def browse_python(self) -> None:
        """浏览Python可执行文件"""
        path, _ = QFileDialog.getOpenFileName(self, "选择Python解释器", "", "Executable (*.exe);;All Files (*)")
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.python_path_edit.setText(os.path.normpath(path))

    def browse_gcc(self) -> None:
        """浏览GCC工具链（mingw64或mingw32目录）"""
        # 选择目录而不是文件
        path = QFileDialog.getExistingDirectory(
            self,
            "选择GCC工具链目录 (mingw64 或 mingw32)",
            GCCDownloader.get_nuitka_cache_dir(),
        )
        if path:
            # 验证mingw目录
            is_valid, msg = validate_mingw_directory(path)
            if not is_valid:
                QMessageBox.critical(
                    self,
                    "GCC工具链验证失败",
                    f"所选目录不是有效的GCC工具链：\n\n{msg}\n\n"
                    "请选择有效的 mingw64 或 mingw32 目录。\n"
                    "该目录应包含 bin 子目录，且 bin 目录下应存在 gcc.exe、g++.exe 等文件。",
                )
                return
            # 规范化路径，统一使用系统默认的路径分隔符
            self.gcc_path_edit.setText(os.path.normpath(path))
            self._show_info("验证通过", "GCC工具链目录验证通过！")

    # =========================================================================
    # 事件处理器
    # =========================================================================

    def on_project_dir_changed(self, text: str) -> None:
        """Handle project directory change"""
        project_dir = text.strip()
        if not project_dir or not os.path.isdir(project_dir):
            return

        # 规范化项目目录路径，统一使用系统默认的路径分隔符
        project_dir = os.path.normpath(project_dir)

        # Check if project directory actually changed
        if project_dir == self._previous_project_dir:
            return

        # Update previous project directory
        self._previous_project_dir = project_dir

        # 重置图标手动选择标志，允许新项目自动加载图标
        self._icon_manually_set = False

        # 检测并清空 build 目录（仅对项目目录操作，单独脚本不处理）
        self._check_and_clean_build_dir(project_dir)

        # Try to find main script - always update when project dir changes
        possible_scripts = ["main.py", "app.py", "run.py", "__main__.py"]
        script_found = False
        for script in possible_scripts:
            script_path = os.path.join(project_dir, script)
            script_path = os.path.normpath(script_path)  # 规范化路径
            if os.path.exists(script_path):
                # 阻止信号避免触发 on_script_path_changed
                self.script_path_edit.blockSignals(True)
                self.script_path_edit.setText(script_path)
                self.script_path_edit.blockSignals(False)
                # 手动更新 _previous_script_path
                self._previous_script_path = script_path
                script_found = True
                break

        # If no common script found, clear the field
        if not script_found:
            self.script_path_edit.blockSignals(True)
            self.script_path_edit.clear()
            self.script_path_edit.blockSignals(False)
            self._previous_script_path = None

        # Set output directory - always update when project dir changes
        output_path = os.path.normpath(os.path.join(project_dir, "build"))
        self.output_dir_edit.setText(output_path)

        # Set program name from directory name - always update when project dir changes
        dir_name = os.path.basename(project_dir)
        if dir_name:
            self.program_name_edit.setText(dir_name)

        # Auto-load icon from project directory - only if user hasn't manually set an icon
        if not self._icon_manually_set:
            self._auto_load_project_icon(project_dir, force_update=True)
        else:
            self.append_log("已保留用户手动选择的图标，跳过自动加载")
        # Reset version info so dialog re-detects from new project
        self._reset_version_info_on_project_change(project_dir)
        # 自动检测版本信息，有结果时自动勾选"添加版权信息"（不触发对话框）
        info = self._detect_version_info_from_project()
        if any(v for v in info.values() if v):
            self.version_info.update(info)
            self.version_info_check.blockSignals(True)
            self.version_info_check.setChecked(True)
            self.version_info_check.blockSignals(False)
            self.append_log("已自动检测到版本信息")

        # 自动判断是否需要显示控制台窗口
        self._console_auto_managed = True
        self._auto_toggle_console_by_script(self.script_path_edit.text().strip(), project_dir)

    def _auto_load_project_icon(self, project_dir: str, force_update: bool = False) -> None:
        """自动从项目目录加载图标（委托给 IconAutoLoader）"""
        if not force_update and self.icon_path_edit.text().strip():
            return

        try:
            icon_path = self.icon_loader.find_icon(project_dir)
            if icon_path:
                self.icon_path_edit.setText(icon_path)
                rel_path = self.icon_loader.get_relative_path(icon_path, project_dir)
                self.append_log(f"已自动加载程序图标: {rel_path}")
            elif force_update:
                self.icon_path_edit.clear()
        except Exception as e:
            print(f"自动加载图标失败: {e}")

    def _reset_version_info_on_project_change(self, project_dir: str) -> None:
        """Reset version info when project changes so it can be re-detected."""
        self.version_info = {
            "product_name": "",
            "company_name": "",
            "file_description": "",
            "copyright": "",
            "version": "",
        }
        if hasattr(self, "version_info_check"):
            self.version_info_check.setChecked(False)
        self.append_log("已重置版权信息（项目已切换）")

    def _on_console_check_changed(self, state: int) -> None:
        """用户手动修改控制台选项后，停止自动管理"""
        self._console_auto_managed = False

    def _auto_toggle_console_by_script(self, script_path: str, project_dir: str) -> None:
        """根据脚本内容自动勾选/取消“显示控制台窗口”"""
        if not self._console_auto_managed:
            return

        if not script_path or not os.path.isfile(script_path):
            return

        has_gui = self._detect_gui_imports(script_path, project_dir)

        # 自动设置时不触发用户变更逻辑
        self.console_check.blockSignals(True)
        self.console_check.setChecked(not has_gui)
        self.console_check.blockSignals(False)

        if has_gui:
            self.append_log("检测到GUI框架，已取消勾选“显示控制台窗口”")
        else:
            self.append_log("未检测到GUI框架，已自动勾选“显示控制台窗口”")

    def _detect_gui_imports(self, script_path: str, project_dir: str) -> bool:
        """检测脚本/项目是否使用GUI框架（委托给 DependencyAnalyzer）"""
        analyzer = DependencyAnalyzer()
        try:
            analyzer.analyze(script_path, project_dir)
            frameworks = analyzer.get_detected_gui_frameworks()
            return bool(frameworks)
        except Exception:
            # 回退：直接检测文件内容
            return self._detect_gui_imports_fallback(script_path, project_dir)

    def _detect_gui_imports_fallback(self, script_path: str, project_dir: str) -> bool:
        """回退：直接用 AST 检测 GUI 导入"""
        gui_modules = {
            "tkinter",
            "customtkinter",
            "pyqt5",
            "pyqt6",
            "pyside2",
            "pyside6",
            "wx",
            "wxpython",
            "kivy",
            "flet",
            "dearpygui",
            "toga",
            "textual",
            "pysimplegui",
            "eel",
            "pygame",
            "qtpy",
        }

        def check_file(path: str) -> bool:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            root = alias.name.split(".")[0].lower()
                            if root in gui_modules:
                                return True
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        root = node.module.split(".")[0].lower()
                        if root in gui_modules:
                            return True
            except Exception:
                return False
            return False

        if check_file(script_path):
            return True

        if project_dir and os.path.isdir(project_dir):
            from utils.constants import SKIP_DIRECTORIES

            skip_dirs = set(SKIP_DIRECTORIES)
            for root, dirs, files in os.walk(project_dir):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for file in files:
                    if file.endswith(".py"):
                        if check_file(os.path.join(root, file)):
                            return True

        return False

    def _check_and_clean_build_dir(self, project_dir: str) -> None:
        """检测项目目录下的 build 目录，如果存在则询问用户是否清空"""
        build_dir = os.path.join(project_dir, "build")

        if not os.path.exists(build_dir) or not os.path.isdir(build_dir):
            return

        # 检查 build 目录是否有内容
        try:
            build_contents = os.listdir(build_dir)
            if not build_contents:
                return  # 空目录，无需清空
        except Exception:
            return

        # 询问用户是否清空 build 目录
        msg_box = self._create_message_box(
            QMessageBox.Icon.Question,
            "清空构建目录",
            f"检测到项目目录下存在 build 目录，其中包含 {len(build_contents)} 个文件/文件夹。\n\n是否清空该目录以确保干净的构建环境？",
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Yes:
            locked_items = []
            failed_items = []
            # 清空 build 目录内容，但保留目录本身
            for item in build_contents:
                item_path = os.path.join(build_dir, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except PermissionError:
                    locked_items.append(item)
                except Exception:
                    failed_items.append(item)

            if locked_items or failed_items:
                if locked_items:
                    self.append_log(f"清理构建目录时发现被占用文件: {', '.join(locked_items)}")
                if failed_items:
                    self.append_log(f"清理构建目录时删除失败: {', '.join(failed_items)}")
                message = "清空构建目录时有部分文件无法删除。\n\n"
                if locked_items:
                    message += f"被占用文件: {', '.join(locked_items)}\n"
                    message += "请先关闭正在运行的 exe 或相关进程后重试。\n"
                if failed_items:
                    message += f"删除失败: {', '.join(failed_items)}\n"
                self._show_warning("警告", message.strip())
            else:
                self.append_log(f"已清空构建目录: {build_dir}")

    def on_script_path_changed(self, text: str) -> None:
        """处理脚本路径变更"""
        script_path = text.strip()
        if not script_path or not os.path.isfile(script_path):
            return

        # 规范化脚本路径，统一使用系统默认的路径分隔符
        script_path = os.path.normpath(script_path)

        # 检查脚本路径是否实际改变
        if script_path == self._previous_script_path:
            return

        script_dir = os.path.dirname(script_path)
        script_dir = os.path.normpath(script_dir)  # 规范化目录路径

        # 获取之前脚本的目录
        previous_script_dir = None
        if self._previous_script_path and os.path.isfile(self._previous_script_path):
            previous_script_dir = os.path.dirname(self._previous_script_path)

        # 更新上一次的脚本路径
        self._previous_script_path = script_path

        # 获取当前项目目录和输出目录的值
        current_project_dir = self.project_dir_edit.text().strip()
        current_output_dir = self.output_dir_edit.text().strip()
        project_dir_changed = False

        # 如果项目目录为空，或者项目目录是之前脚本的目录，则更新为新脚本的目录
        if not current_project_dir or current_project_dir == previous_script_dir:
            # 阻止信号避免触发 on_project_dir_changed
            self.project_dir_edit.blockSignals(True)
            self.project_dir_edit.setText(script_dir)
            self.project_dir_edit.blockSignals(False)
            # 手动更新 _previous_project_dir
            self._previous_project_dir = script_dir
            project_dir_changed = True

        # 如果输出目录为空，或者输出目录是之前脚本目录的build子目录，则更新为新脚本目录的build子目录
        if not current_output_dir or (
            previous_script_dir and current_output_dir == os.path.join(previous_script_dir, "build")
        ):
            output_path = os.path.normpath(os.path.join(script_dir, "build"))
            self.output_dir_edit.setText(output_path)

        # 项目目录由脚本切换时，同步刷新图标/名称/版权信息
        if project_dir_changed:
            if not current_project_dir:
                script_name = os.path.splitext(os.path.basename(script_path))[0]
                if script_name and script_name not in [
                    "main",
                    "app",
                    "run",
                    "__main__",
                ]:
                    self.program_name_edit.setText(script_name)
            else:
                dir_name = os.path.basename(script_dir)
                if dir_name:
                    self.program_name_edit.setText(dir_name)
            if not self._icon_manually_set:
                self._auto_load_project_icon(script_dir, force_update=True)
            self._reset_version_info_on_project_change(script_dir)
            # 自动检测版本信息，有结果时自动勾选"添加版权信息"（不触发对话框）
            info = self._detect_version_info_from_project()
            if any(v for v in info.values() if v):
                self.version_info.update(info)
                self.version_info_check.blockSignals(True)
                self.version_info_check.setChecked(True)
                self.version_info_check.blockSignals(False)
                self.append_log("已自动检测到版本信息")

        # 从脚本名称设置程序名称
        if not project_dir_changed and (not self.program_name_edit.text().strip() or self._is_auto_filled_name()):
            script_name = os.path.splitext(os.path.basename(script_path))[0]
            if script_name and script_name not in ["main", "app", "run", "__main__"]:
                self.program_name_edit.setText(script_name)

        # 自动判断是否需要显示控制台窗口
        self._console_auto_managed = True
        self._auto_toggle_console_by_script(script_path, self.project_dir_edit.text().strip() or script_dir)

    def _is_auto_filled_name(self) -> bool:
        """检查当前程序名称是否为自动填充"""
        current_name = self.program_name_edit.text().strip()
        if not current_name:
            return True

        # 检查名称是否匹配项目目录或脚本名称
        project_dir = self.project_dir_edit.text().strip()
        if project_dir:
            dir_name = os.path.basename(project_dir)
            if current_name == dir_name:
                return True

        script_path = self.script_path_edit.text().strip()
        if script_path:
            script_name = os.path.splitext(os.path.basename(script_path))[0]
            if current_name == script_name:
                return True

        return False

    def on_tool_changed(self, checked: bool) -> None:
        """处理打包工具变更"""
        is_nuitka = self.nuitka_radio.isChecked()

        # Show/hide Nuitka-specific options
        self.gcc_widget.setVisible(is_nuitka)

        # PyInstaller: 隐藏 UPX 选项（由于兼容性问题强制禁用）
        # Nuitka: 显示 UPX 选项（如果用户想用）
        if hasattr(self, "upx_check"):
            self.upx_check.setVisible(is_nuitka)
            if is_nuitka:
                self.upx_check.setChecked(True)
            else:
                self.upx_check.setChecked(False)

        # Load GCC config for Nuitka
        if is_nuitka and not self.gcc_config_loaded and not self.gcc_config_loading:
            self.load_gcc_config()

    def _show_nuitka_options_dialog(self) -> None:
        """显示 Nuitka 高级选项对话框"""
        dialog = NuitkaOptionsDialog(self, self.nuitka_advanced_options, self.theme_manager)
        if dialog.exec() == NuitkaOptionsDialog.DialogCode.Accepted:
            self.nuitka_advanced_options = dialog.get_options()
            self.append_log("已更新 Nuitka 高级选项配置")

    def on_gcc_path_changed(self, text: str) -> None:
        """Handle GCC path change"""
        gcc_path = text.strip()
        if gcc_path:
            self.save_gcc_config()
        # Update download button visibility when GCC path changes
        self._update_gcc_download_button_visibility()

    # =========================================================================
    # Logging
    # =========================================================================

    def append_log(self, message: str) -> None:
        """Append message to log output"""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def clear_log(self) -> None:
        """Clear log output"""
        self.log_text.clear()

    # =========================================================================
    # Log Maximize / Restore
    # =========================================================================

    def _toggle_log_maximize(self) -> None:
        """切换日志输出区域的最大化/还原状态"""
        self._log_maximized = not self._log_maximized

        # 需要隐藏/显示的组件列表
        toggle_widgets = [
            self.file_group,
            self.tool_group,
            self.options_group,
            self.btn_bar_widget,
        ]

        if self._log_maximized:
            # 最大化：隐藏其他区域
            for widget in toggle_widgets:
                widget.setVisible(False)
            self.log_maximize_btn.setToolTip("还原日志")
        else:
            # 还原：显示其他区域
            for widget in toggle_widgets:
                widget.setVisible(True)
            self.log_maximize_btn.setToolTip("最大化日志")

        self._update_log_maximize_btn_icon()

    def _update_log_maximize_btn_icon(self) -> None:
        """根据当前主题和最大化状态更新按钮图标"""
        colors = self.theme_manager.colors
        fg = colors.text_secondary

        if self._log_maximized:
            icon = self._create_restore_icon(fg)
        else:
            icon = self._create_maximize_icon(fg)

        self.log_maximize_btn.setIcon(icon)
        self.log_maximize_btn.setStyleSheet(
            "QPushButton {"
            "  border: none;"
            "  background: transparent;"
            "  padding: 0px;"
            "  min-width: 22px;"
            "  max-width: 22px;"
            "  min-height: 22px;"
            "  max-height: 22px;"
            "}"
            "QPushButton:hover {"
            f"  background: {colors.background_tertiary};"
            "  border-radius: 3px;"
            "}"
        )

    def _copy_all_log(self) -> None:
        """一键复制日志区域的全部内容到剪贴板"""
        log_content = self.log_text.toPlainText()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(log_content)
            self.log_copy_btn.setText("已复制")
            # 1.5秒后恢复按钮文字
            QTimer.singleShot(1500, lambda: self.log_copy_btn.setText("一键复制完整日志"))

    @staticmethod
    def _create_maximize_icon(color: str, size: int = 16) -> QIcon:
        """
        绘制最大化图标（单个矩形 □）

        Args:
            color: 图标颜色
            size: 图标尺寸

        Returns:
            QIcon 对象
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(color), 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))

        m = 2  # margin
        painter.drawRect(m, m, size - 2 * m - 1, size - 2 * m - 1)

        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _create_restore_icon(color: str, size: int = 16) -> QIcon:
        """
        绘制还原图标（两个重叠矩形 ⧉）

        Args:
            color: 图标颜色
            size: 图标尺寸

        Returns:
            QIcon 对象
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(color), 1.3)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))

        # 后方矩形（右上偏移）
        painter.drawRect(5, 1, size - 7, size - 7)
        # 前方矩形（左下偏移）
        painter.drawRect(1, 5, size - 7, size - 7)

        painter.end()
        return QIcon(pixmap)

    # =========================================================================
    # Configuration
    # =========================================================================

    def get_config(self) -> PackagingConfig:
        """获取打包配置（返回类型化的 PackagingConfig）"""
        return self.config_marshaller.marshall(
            script_path_edit=self.script_path_edit.text(),
            output_dir_edit=self.output_dir_edit.text(),
            icon_path_edit=self.icon_path_edit.text(),
            program_name_edit=self.program_name_edit.text(),
            python_path_edit=self.python_path_edit.text(),
            gcc_path_edit=self.gcc_path_edit.text(),
            is_nuitka=self.nuitka_radio.isChecked(),
            onefile=self.onefile_check.isChecked(),
            console=self.console_check.isChecked(),
            clean=self.clean_check.isChecked(),
            upx=self.upx_check.isChecked(),
            use_venv=self.venv_check.isChecked(),
            version_info=self.version_info,
            has_version_info=self.version_info_check.isChecked(),
            nuitka_advanced_options=self.nuitka_advanced_options,
            exclude_modules_text=self.exclude_modules_edit.text(),
        )

    # =========================================================================
    # Button State Management
    # =========================================================================

    def set_buttons_enabled(self, enabled: bool) -> None:
        """Set button enabled states"""
        self.package_btn.setEnabled(enabled)
        self.analyze_btn.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)

    def _set_cancel_button_style(self) -> None:
        """Set cancel button red warning style"""
        style = self.theme_manager.get_danger_button_style()
        self.package_btn.setStyleSheet(style)

    def _reset_package_button_style(self) -> None:
        """Reset package button to default style"""
        self.package_btn.setStyleSheet("")

    # =========================================================================
    # Message Box Helpers
    # =========================================================================

    def _create_message_box(self, icon_type: QMessageBox.Icon, title: str, text: str) -> QMessageBox:
        """Create themed message box"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(icon_type)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setStyleSheet(self.theme_manager.get_message_box_style())
        return msg_box

    def _show_info(self, title: str, text: str) -> None:
        """Show information message box"""
        msg_box = self._create_message_box(QMessageBox.Icon.Information, title, text)
        msg_box.exec()

    def _show_warning(self, title: str, text: str) -> None:
        """Show warning message box"""
        msg_box = self._create_message_box(QMessageBox.Icon.Warning, title, text)
        msg_box.exec()

    def _show_error(self, title: str, text: str) -> None:
        """Show error message box"""
        msg_box = self._create_message_box(QMessageBox.Icon.Critical, title, text)
        msg_box.exec()

    # =========================================================================
    # Dependency Analysis
    # =========================================================================

    def analyze_dependencies(self) -> None:
        """Analyze project dependencies"""
        script_path = self.script_path_edit.text().strip()
        if not script_path:
            self._show_warning("警告", "请先选择运行脚本！")
            return

        if not os.path.exists(script_path):
            self._show_warning("警告", "脚本文件不存在！")
            return

        self.log_text.clear()
        self.append_log("=" * 50)
        self.append_log("开始分析项目依赖...")
        self.append_log("=" * 50)

        self.set_buttons_enabled(False)

        project_dir = self.project_dir_edit.text().strip()

        def task():
            try:
                analyzer = DependencyAnalyzer()

                def log_callback(msg: str) -> None:
                    self.log_signal.emit(msg)

                self.log_signal.emit(f"分析脚本: {script_path}")

                # Analyze dependencies - returns a Set[str]
                deps = analyzer.analyze(script_path, project_dir or None)

                self.log_signal.emit("\n发现的依赖模块:")
                for dep in sorted(deps):
                    self.log_signal.emit(f"  - {dep}")

                # Find excludable modules using existing method
                excludable = analyzer.get_exclude_modules()
                if excludable:
                    exclude_str = ",".join(excludable)
                    self.update_exclude_modules_signal.emit(exclude_str)
                    self.log_signal.emit(f"\n建议排除的模块: {exclude_str}")

                self.log_signal.emit("\n" + "=" * 50)
                self.log_signal.emit("依赖分析完成！")
                self.log_signal.emit("=" * 50)

            except Exception as e:
                self.log_signal.emit(f"分析过程发生错误: {str(e)}")
            finally:
                # Re-enable buttons via signal
                self.analyze_finished_signal.emit()

        threading.Thread(target=task, daemon=True).start()

    @pyqtSlot()
    def _on_analyze_finished(self) -> None:
        """Handle analyze finished"""
        self.set_buttons_enabled(True)

    def update_exclude_modules_ui(self, modules: str) -> None:
        """Update exclude modules text"""
        current = self.exclude_modules_edit.text().strip()
        if current:
            # Merge with existing
            existing = set(m.strip() for m in current.split(",") if m.strip())
            new_modules = set(m.strip() for m in modules.split(",") if m.strip())
            merged = existing.union(new_modules)
            self.exclude_modules_edit.setText(",".join(sorted(merged)))
        else:
            self.exclude_modules_edit.setText(modules)

    def update_download_progress_ui(self, progress: str) -> None:
        """Update download progress label"""
        self.gcc_download_label.setText(progress)

    def _on_gcc_download_complete(self, gcc_path: str) -> None:
        """处理 GCC 下载完成"""
        self.gcc_path_edit.setText(gcc_path)
        self.save_gcc_config()

    def _on_gcc_download_reset_button(self) -> None:
        """重置 GCC 下载按钮状态"""
        self.gcc_download_btn.setText("自动下载")
        self.gcc_download_btn.setStyleSheet("")

    # =========================================================================
    # GCC Configuration
    # =========================================================================

    def get_nuitka_cache_dir(self) -> str:
        """Get Nuitka cache directory"""
        user_home = os.path.expanduser("~")
        return os.path.join(user_home, "AppData", "Local", "Nuitka", "Nuitka", "Cache", "downloads")

    def find_gcc_in_cache(self) -> Optional[str]:
        """Find GCC mingw directory in Nuitka cache"""
        # 使用GCCDownloader的静态方法查找有效的mingw目录
        return GCCDownloader.get_default_mingw_path()

    def load_gcc_config(self) -> None:
        """Load GCC configuration (mingw directory)"""
        if self.gcc_config_loading:
            return

        self.gcc_config_loading = True

        try:
            # 首先尝试从配置文件加载
            if os.path.exists(self.gcc_config_file):
                with open(self.gcc_config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    gcc_path = config.get("gcc_path", "")
                    if gcc_path and os.path.exists(gcc_path):
                        # 验证路径是否是有效的mingw目录
                        is_valid, _ = validate_mingw_directory(gcc_path)
                        if is_valid:
                            self.gcc_path_edit.setText(gcc_path)
                            self.gcc_config_loaded = True
                            self.gcc_config_loading = False
                            self._update_gcc_download_button_visibility()
                            return

            # 尝试在Nuitka缓存中查找mingw目录
            cached_gcc = self.find_gcc_in_cache()
            if cached_gcc:
                self.gcc_path_edit.setText(cached_gcc)
                self.save_gcc_config()

            self.gcc_config_loaded = True
            self._update_gcc_download_button_visibility()

        except Exception as e:
            print(f"加载GCC配置失败: {e}")
        finally:
            self.gcc_config_loading = False

    def _update_gcc_download_button_visibility(self) -> None:
        """根据GCC路径可用性更新GCC下载按钮的可见性"""
        gcc_path = self.gcc_path_edit.text().strip()
        # Hide the download button if GCC path is set and is a valid mingw directory
        if gcc_path and os.path.exists(gcc_path):
            is_valid, _ = validate_mingw_directory(gcc_path)
            if is_valid:
                self.gcc_download_btn.setVisible(False)
                return
        # Show the download button if no valid GCC path
        self.gcc_download_btn.setVisible(True)

    def save_gcc_config(self) -> None:
        """保存GCC配置"""
        try:
            gcc_path = self.gcc_path_edit.text().strip()
            config = {"gcc_path": gcc_path}
            with open(self.gcc_config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存GCC配置失败: {e}")

    def download_gcc(self) -> None:
        """下载GCC工具链（支持多线程下载、重试、验证和自动解压）"""
        if self.is_downloading:
            # 取消下载
            self.cancel_download = True
            self.gcc_download_btn.setText("自动下载")
            self.gcc_download_btn.setStyleSheet("")  # 重置为默认样式
            self.gcc_download_label.setText("正在取消...")
            return

        self.is_downloading = True
        self.cancel_download = False
        self.gcc_download_btn.setText("取消下载")
        # 应用与取消打包按钮相同的危险按钮样式
        style = self.theme_manager.get_danger_button_style()
        self.gcc_download_btn.setStyleSheet(style)
        self.gcc_download_label.setText("准备下载...")

        def download_task():
            try:
                # 创建日志和进度回调
                def log_callback(msg: str) -> None:
                    self.log_signal.emit(msg)

                def progress_callback(msg: str) -> None:
                    self.update_download_progress_signal.emit(msg)

                def cancel_check() -> bool:
                    return self.cancel_download

                # 使用GCCDownloader进行下载和解压
                downloader = GCCDownloader(
                    log_callback=log_callback,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )

                # 首先检查是否已存在有效的mingw目录
                existing_mingw = downloader.find_existing_gcc()
                if existing_mingw:
                    self.update_download_progress_signal.emit("发现已存在的有效GCC工具链")
                    self.gcc_download_complete_signal.emit(existing_mingw)
                    self.update_download_progress_signal.emit("已加载现有工具链")
                    return

                # 执行下载和解压（download方法会自动下载、验证、解压并返回mingw目录路径）
                result_path = downloader.download()

                if self.cancel_download:
                    self.update_download_progress_signal.emit("下载已取消")
                elif result_path:
                    self.update_download_progress_signal.emit("下载并解压完成！")
                    # 在UI中更新GCC路径（result_path现在是mingw目录）
                    self.gcc_download_complete_signal.emit(result_path)
                else:
                    self.update_download_progress_signal.emit("下载失败，请重试")
                    self._show_gcc_download_failed_dialog()

            except Exception as e:
                self.update_download_progress_signal.emit(f"下载出错: {str(e)}")
                self._show_gcc_download_failed_dialog()
            finally:
                self.is_downloading = False
                self.gcc_download_reset_button_signal.emit()

        self.download_thread = threading.Thread(target=download_task, daemon=True)
        self.download_thread.start()

    @pyqtSlot()
    def _show_gcc_download_failed_dialog(self) -> None:
        """Show dialog when GCC download fails, prompting user to download manually"""
        # 根据系统架构提示下载对应版本
        arch = GCCDownloader.get_system_arch()
        if arch == "x86_64":
            arch_hint = "x86_64-posix-seh"
        else:
            arch_hint = "i686-posix-dwarf"

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("GCC下载失败")
        msg_box.setText(
            "自动下载GCC工具链失败，可能是网络问题。\n\n"
            "您可以：\n"
            "1. 点击「重试」再次尝试自动下载\n"
            "2. 点击「手动下载」打开下载页面，下载zip文件后手动解压到：\n"
            f"   {GCCDownloader.get_nuitka_cache_dir()}\n"
            "   然后使用「浏览」按钮选择解压后的 mingw64 或 mingw32 目录\n\n"
            "下载地址：\n"
            "https://github.com/brechtsanders/winlibs_mingw/releases/latest\n\n"
            f"请下载包含 {arch_hint} 的zip文件（当前系统架构: {arch}）。"
        )
        retry_btn = msg_box.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
        manual_btn = msg_box.addButton("手动下载", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        clicked_btn = msg_box.clickedButton()
        if clicked_btn == retry_btn:
            # 重新开始下载
            self.download_gcc()
        elif clicked_btn == manual_btn:
            # 打开浏览器
            webbrowser.open("https://github.com/brechtsanders/winlibs_mingw/releases/latest")

    # =========================================================================
    # Packaging Operations
    # =========================================================================

    def toggle_packaging(self) -> None:
        """Toggle packaging state"""
        if self.is_packaging:
            self.cancel_packaging_process()
        else:
            self.start_packaging()

    def cancel_packaging_process(self) -> None:
        """Cancel packaging process"""
        self.append_log("\n请求取消打包...")
        self.cancel_packaging = True

        # Terminate packaging process
        if self.packaging_process:
            try:
                self.packaging_process.terminate()
                self.append_log("正在终止打包进程...")
                # 尝试强制终止
                try:
                    self.packaging_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.packaging_process.kill()
                    self.append_log("已强制终止进程")
            except Exception as e:
                self.append_log(f"终止进程时出错: {str(e)}")

        # Cancel worker if using QThreadPool
        if self._current_packaging_worker:
            self._current_packaging_worker.cancel()

        # 更新按钮文本显示取消中状态，但不完全重置
        # 状态重置会在 on_packaging_finished 中完成
        self.package_btn.setText("取消中...")
        self.package_btn.setEnabled(False)

    def start_packaging(self) -> None:
        """Start packaging process"""
        script_path = self.script_path_edit.text().strip()
        if not script_path:
            self._show_warning("警告", "请选择运行脚本！")
            return

        if not os.path.exists(script_path):
            self._show_warning("警告", "脚本文件不存在！")
            return

        # Validate GCC path for Nuitka
        if self.nuitka_radio.isChecked():
            gcc_path = self.gcc_path_edit.text().strip()
            if gcc_path and not gcc_path.endswith(".zip") and not os.path.isdir(gcc_path):
                self._show_warning("警告", "GCC路径必须是.zip文件或目录！")
                return

        config = self.get_config()

        self.log_text.clear()
        self.append_log("=" * 50)
        self.append_log("开始打包流程...")
        self.append_log(f"工具: {config.tool}")
        self.append_log(f"脚本: {config.script_path}")
        if config.exclude_modules:
            self.append_log(f"排除模块: {', '.join(config.exclude_modules)}")
        self.append_log("=" * 50)

        # Set packaging state
        self.is_packaging = True
        self.cancel_packaging = False
        self.packaging_process = None
        self.package_btn.setText("取消打包")
        self._set_cancel_button_style()

        # Disable other buttons
        self.analyze_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        def task():
            try:

                def log_callback(msg: str) -> None:
                    self.log_signal.emit(msg)

                def process_callback(process: subprocess.Popen) -> None:
                    self.packaging_process = process

                packager = Packager()
                success, message, exe_path = packager.package_via_pipeline(
                    config,
                    log_callback=log_callback,
                    cancel_flag=lambda: self.cancel_packaging,
                    process_callback=process_callback,
                )

                if success:
                    self.log_signal.emit("\n" + "=" * 50)
                    self.log_signal.emit("打包成功！")
                    self.log_signal.emit("=" * 50)

                    # 添加图标相关提示
                    icon_path = config.icon_path
                    if icon_path:
                        self.log_signal.emit("\n【图标说明】")
                        self.log_signal.emit(f"  已使用图标: {icon_path}")
                        self.log_signal.emit("")
                        self.log_signal.emit("  如果 exe 文件图标显示不正确：")
                        self.log_signal.emit("  ─────────────────────────────────")
                        self.log_signal.emit("  1. Windows 图标缓存问题（最常见）:")
                        self.log_signal.emit("     • 方法A: 在任务管理器中重启 explorer.exe")
                        self.log_signal.emit("     • 方法B: 运行命令 ie4uinit.exe -show")
                        self.log_signal.emit("     • 方法C: 重新登录 Windows 账户或重启电脑")
                        self.log_signal.emit("")
                        self.log_signal.emit("  2. 验证 exe 实际嵌入的图标:")
                        self.log_signal.emit("     • 右键点击 exe 文件 → 属性 → 详细信息")
                        self.log_signal.emit("     • 或使用 Resource Hacker 工具查看 exe 资源")
                        self.log_signal.emit("")
                        self.log_signal.emit("  3. 运行时窗口/任务栏图标不显示:")
                        self.log_signal.emit("     • 这需要在应用程序代码中设置，打包工具无法自动处理")
                        self.log_signal.emit("     • PyQt/PySide: app.setWindowIcon(QIcon('icon.ico'))")
                        self.log_signal.emit("     • Tkinter: root.iconbitmap('icon.ico')")
                        self.log_signal.emit("     • 图标文件需通过 extra_data 选项包含到打包中")

                    self.finished_signal.emit(True, message)

                    if exe_path:
                        self.open_output_directory(exe_path)
                else:
                    self.log_signal.emit("\n" + "=" * 50)
                    self.log_signal.emit("打包失败！")
                    self.log_signal.emit("=" * 50)
                    self.finished_signal.emit(False, message)

            except Exception as e:
                self.log_signal.emit(f"打包过程发生错误: {str(e)}")
                self.finished_signal.emit(False, str(e))

        threading.Thread(target=task, daemon=True).start()

    def on_packaging_finished(self, success: bool, message: str) -> None:
        """Handle packaging finished"""
        # Reset state
        was_cancelled = self.cancel_packaging

        self.is_packaging = False
        self.cancel_packaging = False
        self.packaging_process = None
        self._current_packaging_worker = None
        self.package_btn.setText("开始打包")
        self.package_btn.setEnabled(True)
        self._reset_package_button_style()

        self.set_buttons_enabled(True)

        # Don't show message box if cancelled
        if was_cancelled:
            self.append_log("打包已取消")
            return

        if success:
            self._show_info("成功", message)
        else:
            self._show_error("失败", message)

    def open_output_directory(self, exe_path: str) -> None:
        """Open output directory and select the exe file"""
        try:
            import platform

            if not os.path.exists(exe_path):
                self.append_log(f"文件不存在: {exe_path}")
                return

            directory = os.path.dirname(exe_path)
            system = platform.system()

            if system == "Windows":
                # 使用 os.startfile 打开目录，避免 explorer 的路径问题
                # 或使用 shell=True 的方式调用 explorer
                try:
                    # 方法1：直接打开目录（更稳定）
                    os.startfile(directory)
                except Exception:
                    # 方法2：使用 shell 命令打开并选中文件
                    try:
                        normalized_path = os.path.normpath(exe_path)
                        # 使用 shell=True 避免路径解析问题
                        subprocess.run(
                            f'explorer /select,"{normalized_path}"',
                            shell=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    except Exception:
                        # 方法3：仅打开目录
                        subprocess.run(
                            f'explorer "{os.path.normpath(directory)}"',
                            shell=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", exe_path])
            else:
                try:
                    subprocess.Popen(["xdg-open", directory])
                except Exception:
                    subprocess.Popen(["nautilus", directory])

            self.append_log(f"\n已打开输出目录: {directory}")

        except Exception as e:
            self.append_log(f"打开目录时出错: {str(e)}")
