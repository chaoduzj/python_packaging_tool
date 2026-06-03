"""
pytest 配置和共享 fixtures
"""

import os
import sys
import tempfile
import shutil

import pytest

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def temp_dir():
    """创建临时目录，测试结束后自动清理"""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_script(temp_dir):
    """创建一个示例 Python 脚本"""
    script_path = os.path.join(temp_dir, "sample.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("""
import os
import sys
import json
import requests
from pathlib import Path

def main():
    print("Hello World")

if __name__ == "__main__":
    main()
""")
    return script_path


@pytest.fixture
def sample_gui_script(temp_dir):
    """创建一个 GUI 示例脚本"""
    script_path = os.path.join(temp_dir, "gui_sample.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
""")
    return script_path


@pytest.fixture
def sample_project(temp_dir):
    """创建一个示例项目结构"""
    # 创建主脚本
    main_script = os.path.join(temp_dir, "main.py")
    with open(main_script, "w", encoding="utf-8") as f:
        f.write("""
import os
import sys
from utils.helper import do_something
import requests

def main():
    do_something()

if __name__ == "__main__":
    main()
""")

    # 创建子模块
    utils_dir = os.path.join(temp_dir, "utils")
    os.makedirs(utils_dir)
    with open(os.path.join(utils_dir, "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(utils_dir, "helper.py"), "w", encoding="utf-8") as f:
        f.write("""
import json
import numpy as np

def do_something():
    data = {"key": "value"}
    arr = np.array([1, 2, 3])
    return json.dumps(data), arr
""")

    # 创建 requirements.txt
    req_path = os.path.join(temp_dir, "requirements.txt")
    with open(req_path, "w", encoding="utf-8") as f:
        f.write("requests==2.31.0\nnumpy>=1.24.0\n")

    return temp_dir, main_script


@pytest.fixture
def log_messages():
    """收集日志消息的 fixture"""
    messages = []

    def log_callback(msg):
        messages.append(msg)

    return messages, log_callback


@pytest.fixture
def minimal_packable_project(temp_dir):
    """创建一个最小可打包项目（仅依赖标准库，避免网络依赖）。

    用于端到端打包冒烟测试。返回 (project_dir, main_script, output_dir)。
    """
    main_script = os.path.join(temp_dir, "main.py")
    with open(main_script, "w", encoding="utf-8") as f:
        f.write(
            "import sys\n"
            "import os\n"
            "import json\n"
            "\n"
            "def main():\n"
            "    data = {'msg': 'hello from packaged exe'}\n"
            "    print(json.dumps(data))\n"
            "    return 0\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    sys.exit(main())\n"
        )

    output_dir = os.path.join(temp_dir, "build")
    return temp_dir, main_script, output_dir
