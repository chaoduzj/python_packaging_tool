"""问题反馈对话框 — 从 main_window 抽离。

设计要点：
- 不持有任何业务状态，所有数据通过构造参数注入
- 主题样式通过 theme_manager 注入，与主窗口保持一致
- 提供 show() 类方法以便主窗口一行调用
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt


def _copy_selected_text(label: QLabel) -> None:
    """复制 QLabel 中选中的文本到剪贴板（无业务依赖的纯函数）。"""
    selected_text = label.selectedText()
    if selected_text:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(selected_text)


class FeedbackDialog(QDialog):
    """问题反馈对话框。

    Args:
        parent: 父窗口
        theme_manager: 主题管理器（提供 colors / is_dark）
        app_name: 应用名称
        display_version: 显示版本号
        author_email: 作者邮箱
        show_vip_privilege: 是否显示捐赠用户特权说明
        config: 当前打包配置（dict 或 PackagingConfig，取 tool/onefile 等字段）
        log_text: 日志文本（用于显示和复制）
    """

    def __init__(
        self,
        parent,
        theme_manager,
        app_name: str,
        display_version: str,
        author_email: str,
        show_vip_privilege: bool,
        config: Any,
        log_text: str,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._app_name = app_name
        self._display_version = display_version
        self._author_email = author_email
        self._show_vip_privilege = show_vip_privilege
        self._config = config
        self._log_text = log_text
        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle("问题反馈")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        colors = self._theme_manager.colors
        self.setStyleSheet(f"""
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

        layout = QVBoxLayout(self)

        # 软件信息（包含版本号）
        info_label = QLabel(
            f"<h3>{self._app_name}</h3><p><b>软件版本：</b>{self._display_version}</p>"
        )
        layout.addWidget(info_label)

        # 当前配置信息
        config_text = self._format_config_text()
        config_label = QLabel(config_text)
        config_label.setWordWrap(True)
        layout.addWidget(config_label)

        # 日志信息
        log_label = QLabel("<b>日志输出：</b>")
        layout.addWidget(log_label)

        log_text_widget = QTextEdit()
        log_text_widget.setReadOnly(True)
        log_text_widget.setPlainText(self._log_text)
        log_text_widget.setMaximumHeight(200)
        layout.addWidget(log_text_widget)

        # 专属特权说明
        if self._show_vip_privilege:
            highlight_color = "#FFD700" if self._theme_manager.is_dark else "#FF0000"
            vip_label = QLabel(
                f"<br><span style='color: {highlight_color};'>捐赠用户在遇到打包问题时，将<b>优先获得技术支持和问题排查协助</b>。</span><br>"
            )
            layout.addWidget(vip_label)

        # 作者邮箱（带右键菜单）
        email_label = QLabel(f"<b>作者邮箱：</b> {self._author_email}")
        email_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        email_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        email_label.customContextMenuRequested.connect(
            lambda pos: self._show_email_context_menu(email_label, pos)
        )
        layout.addWidget(email_label)

        # 提示信息
        tip_label = QLabel(
            "<br><i>请将以上信息复制后发送到邮箱，以便我们更好地帮助您解决问题。</i>"
        )
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        # 按钮区
        btn_layout = QHBoxLayout()

        copy_btn = QPushButton("一键复制")
        copy_btn.setProperty("buttonType", "primary")
        copy_btn.clicked.connect(self._copy_all)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # 内部 helpers
    # ------------------------------------------------------------------
    def _config_get(self, key: str, default=None):
        """同时兼容 dict 与 PackagingConfig 两种 config 形态。"""
        cfg = self._config
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        # PackagingConfig：优先用属性访问，回退到 get
        getter = getattr(cfg, "get", None)
        if callable(getter):
            return getter(key, default)
        return getattr(cfg, key, default)

    def _format_config_text(self) -> str:
        return f"""
<b>当前打包配置：</b><br>
- 打包工具: {self._config_get('tool', 'N/A')}<br>
- 单文件模式: {"是" if self._config_get('onefile') else "否"}<br>
- 显示控制台: {"是" if self._config_get('console') else "否"}<br>
- 清理构建缓存: {"是" if self._config_get('clean') else "否"}<br>
- 使用UPX压缩: {"是" if self._config_get('upx') else "否"}<br>
- 脚本路径: {self._config_get('script_path') or 'N/A'}<br>
- 项目目录: {self._config_get('project_dir') or 'N/A'}<br>
- 输出目录: {self._config_get('output_dir') or 'N/A'}<br>
"""

    def _show_email_context_menu(self, email_label: QLabel, pos) -> None:
        """显示邮箱的中文右键菜单。"""
        colors = self._theme_manager.colors
        context_menu = QMenu(email_label)
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

        copy_action = QAction("复制", email_label)
        copy_action.triggered.connect(lambda: _copy_selected_text(email_label))
        context_menu.addAction(copy_action)
        context_menu.exec(email_label.mapToGlobal(pos))

    def _copy_all(self) -> None:
        """一键复制反馈内容到剪贴板。"""
        full_text = f"""{self._app_name} - 问题反馈
软件版本：{self._display_version}

当前打包配置：
- 打包工具: {self._config_get('tool', 'N/A')}
- 单文件模式: {"是" if self._config_get('onefile') else "否"}
- 显示控制台: {"是" if self._config_get('console') else "否"}
- 清理构建缓存: {"是" if self._config_get('clean') else "否"}
- 使用UPX压缩: {"是" if self._config_get('upx') else "否"}
- 脚本路径: {self._config_get('script_path') or 'N/A'}
- 项目目录: {self._config_get('project_dir') or 'N/A'}
- 输出目录: {self._config_get('output_dir') or 'N/A'}

日志输出：
{self._log_text}
"""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(full_text)
            QMessageBox.information(self, "提示", "已复制到剪贴板！")


def show_feedback_dialog(
    parent,
    theme_manager,
    app_name: str,
    display_version: str,
    author_email: str,
    show_vip_privilege: bool,
    config: Any,
    log_text: str,
) -> None:
    """便捷入口：构造并模态显示问题反馈对话框。"""
    dialog = FeedbackDialog(
        parent=parent,
        theme_manager=theme_manager,
        app_name=app_name,
        display_version=display_version,
        author_email=author_email,
        show_vip_privilege=show_vip_privilege,
        config=config,
        log_text=log_text,
    )
    dialog.exec()
