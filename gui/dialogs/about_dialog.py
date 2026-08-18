"""关于对话框 — 从 main_window 抽离。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


class AboutDialog(QDialog):
    """关于对话框（图标 + HTML 说明 + 关闭按钮）。"""

    def __init__(
        self,
        parent,
        theme_manager,
        window_icon: QIcon,
        about_html: str,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._window_icon = window_icon
        self._about_html = about_html
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("关于")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        self.setWindowIcon(self._window_icon)

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

        layout = QVBoxLayout(self)

        # 顶部图标 + 说明
        top_layout = QHBoxLayout()

        icon_label = QLabel()
        icon_pixmap = self._window_icon.pixmap(64, 64)
        if not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(icon_label)

        top_layout.addSpacing(10)

        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(False)
        text_browser.setHtml(self._about_html)
        text_browser.setMinimumHeight(150)
        top_layout.addWidget(text_browser)

        layout.addLayout(top_layout)

        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


def show_about_dialog(parent, theme_manager, window_icon: QIcon, about_html: str) -> None:
    """便捷入口：构造并模态显示关于对话框。"""
    dialog = AboutDialog(parent, theme_manager, window_icon, about_html)
    dialog.exec()
