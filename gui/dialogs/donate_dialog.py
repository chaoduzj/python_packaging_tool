"""捐赠对话框 — 从 main_window 抽离。

设计要点：
- 倒计时逻辑封装在内部，不污染主窗口状态（移除了 self._countdown 共享）
- 二维码图片路径解析逻辑独立为函数，便于复用
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _resolve_resource_base(caller_file: str) -> str:
    """解析资源根目录。

    打包后（cx_Freeze/PyInstaller/Nuitka）从 exe 同级目录查找；
    开发模式下从项目根目录（caller_file 的上两级）查找。
    """
    if getattr(sys, "frozen", False) or "__compiled__" in dir():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(caller_file))


class DonateDialog(QDialog):
    """捐赠对话框（含二维码 + 3 秒倒计时启用关闭按钮）。"""

    def __init__(self, parent, theme_manager, caller_file: str) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._caller_file = caller_file
        self._countdown = 3  # 仅本对话框内部使用
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("☕ 请作者喝杯咖啡")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)

        colors = self._theme_manager.colors
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
            }}
            QLabel {{
                color: {colors.text_primary};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        # 感谢语与特权说明
        highlight_color = "#FFD700" if self._theme_manager.is_dark else "#FF0000"
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

        alipay_widget = self._create_qr_widget("alipay.jpg", "支付宝")
        wechat_widget = self._create_qr_widget("wechat_pay.png", "微信支付")
        qr_layout.addWidget(alipay_widget)
        qr_layout.addWidget(wechat_widget)
        layout.addLayout(qr_layout)

        # 底部关闭按钮（前 3 秒禁用，防止误关）
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("感谢支持 (3s)")
        close_btn.setMinimumWidth(120)
        close_btn.setMinimumHeight(35)
        close_btn.setProperty("buttonType", "primary")
        close_btn.setEnabled(False)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # 3 秒倒计时，逐步启用关闭按钮
        def tick():
            self._countdown -= 1
            if self._countdown > 0:
                close_btn.setText(f"感谢支持 ({self._countdown}s)")
            else:
                close_btn.setText("感谢支持")
                close_btn.setEnabled(True)
                timer.stop()

        timer = QTimer(self)
        timer.timeout.connect(tick)
        timer.start(1000)

    def _create_qr_widget(self, img_name: str, title: str) -> QWidget:
        """创建单个二维码展示组件（图片 + 标题）。"""
        widget = QWidget()
        v_layout = QVBoxLayout(widget)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        base = _resolve_resource_base(self._caller_file)
        img_path = os.path.join(base, "resources", img_name)
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

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            "font-weight: bold; font-size: 15px; margin-top: 5px;"
        )
        v_layout.addWidget(title_label)

        return widget


def show_donate_dialog(parent, theme_manager, caller_file: str) -> None:
    """便捷入口：构造并模态显示捐赠对话框。"""
    dialog = DonateDialog(parent, theme_manager, caller_file)
    dialog.exec()
