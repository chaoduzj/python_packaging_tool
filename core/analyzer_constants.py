"""
依赖分析器常量定义模块

本模块包含 DependencyAnalyzer 使用的所有常量定义，包括：
- Python 标准库模块列表
- 大型包及其子模块
- 开发/测试相关的包
- GUI 框架映射
- Qt 绑定包列表
- 已配置库列表
"""

from typing import Dict, List, Set, Tuple

# Python标准库列表（部分常用的）
STDLIB_MODULES: Set[str] = {
    "abc",
    "aifc",
    "argparse",
    "array",
    "ast",
    "asynchat",
    "asyncio",
    "asyncore",
    "atexit",
    "audioop",
    "base64",
    "bdb",
    "binascii",
    "binhex",
    "bisect",
    "builtins",
    "bz2",
    "calendar",
    "cgi",
    "cgitb",
    "chunk",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "crypt",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "distutils",
    "doctest",
    "email",
    "encodings",
    "ensurepip",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "formatter",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "grp",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "idlelib",
    "imaplib",
    "imghdr",
    "imp",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "lib2to3",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "msilib",
    "msvcrt",
    "multiprocessing",
    "netrc",
    "nis",
    "nntplib",
    "numbers",
    "operator",
    "optparse",
    "os",
    "ossaudiodev",
    "parser",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pipes",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "posixpath",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "spwd",
    "sqlite3",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symbol",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "test",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "turtledemo",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "winreg",
    "winsound",
    "wsgiref",
    "xdrlib",
    "xml",
    "xmlrpc",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
    "__future__",
    "__main__",
}

# 常见的大型库及其子模块（打包时可能需要排除）
LARGE_PACKAGES: Dict[str, List[str]] = {
    "numpy": ["numpy.tests", "numpy.f2py.tests"],
    "pandas": ["pandas.tests"],
    "scipy": ["scipy.tests"],
    "matplotlib": ["matplotlib.tests", "matplotlib.sphinxext"],
    "sklearn": ["sklearn.tests"],
    "torch": ["torch.testing", "torch.utils.tensorboard"],
    "tensorflow": ["tensorflow.python.debug", "tensorflow.lite"],
    "PIL": ["PIL.tests"],
    "cv2": [],
    "pytest": [],
    "unittest": [],
    "doctest": [],
    "pdb": [],
    "IPython": [],
    "jupyter": [],
    "notebook": [],
}

# 开发/测试相关的包（通常不需要打包）
DEV_PACKAGES: Set[str] = {
    "pytest",
    "unittest",
    "nose",
    "tox",
    "coverage",
    "black",
    "flake8",
    "pylint",
    "mypy",
    "isort",
    "autopep8",
    "yapf",
    "bandit",
    "safety",
    "pip",
    "setuptools",
    "wheel",
    "twine",
    "sphinx",
    "ipython",
    "jupyter",
    "notebook",
    "ipykernel",
    "ipywidgets",
}

# GUI 框架映射表（PyPI 包名 -> Python 导入名）
GUI_FRAMEWORK_MAPPING: Dict[str, str] = {
    # Qt 系列
    "PyQt6": "PyQt6",
    "PyQt5": "PyQt5",
    "PySide6": "PySide6",
    "PySide2": "PySide2",
    # wxPython 系列
    "wxPython": "wx",
    "wax": "wax",
    # Tkinter 系列
    "customtkinter": "customtkinter",
    # PySimpleGUI 系列
    "PySimpleGUI": "PySimpleGUI",
    "PySimpleGUIQt": "PySimpleGUIQt",
    "PySimpleGUIWx": "PySimpleGUIWx",
    "PySimpleGUIWeb": "PySimpleGUIWeb",
    # 其他 GUI 框架
    "kivy": "kivy",
    "flet": "flet",
    "dearpygui": "dearpygui",
    "DearPyGui": "dearpygui",
    "eel": "eel",
    "toga": "toga",
    "textual": "textual",
    "pyforms": "pyforms",
    "pyforms-gui": "pyforms_gui",
    "libavg": "libavg",
    "pygui": "GUI",
}

# 需要包含数据文件的框架
FRAMEWORKS_WITH_DATA_FILES: Dict[str, List[Tuple[str, str]]] = {
    "customtkinter": [
        # CustomTkinter 需要主题 JSON 文件
        ("customtkinter", "customtkinter"),
    ],
    "kivy": [
        # Kivy 需要 data 目录（字体、图片等）
        ("kivy/data", "kivy/data"),
        ("kivy/tools", "kivy/tools"),
    ],
    "flet": [
        # Flet 需要 Flutter 引擎
        ("flet", "flet"),
        ("flet_core", "flet_core"),
        ("flet_runtime", "flet_runtime"),
    ],
    "dearpygui": [
        # DearPyGui 需要核心 DLL
        ("dearpygui", "dearpygui"),
    ],
    "textual": [
        # Textual 需要 CSS 样式文件
        ("textual", "textual"),
    ],
    "wxpython": [
        # wxPython 需要 locale 目录（语言文件）和 DLL
        ("wx/locale", "wx/locale"),
    ],
    "pygame": [
        # Pygame 需要资源目录
        ("pygame", "pygame"),
    ],
    "pyglet": [
        # Pyglet 需要资源文件
        ("pyglet", "pyglet"),
    ],
}

# Nuitka 框架专用选项映射表
# key: GUI 框架名称（小写）, value: 需要追加的 Nuitka 命令行参数列表
NUITKA_FRAMEWORK_OPTIONS: Dict[str, List[str]] = {
    "wxpython": [
        "--include-package=wx",
        "--enable-plugin=multiprocessing",
    ],
    "kivy": [
        "--include-package=kivy",
    ],
    "flet": [
        "--include-package=flet",
        "--include-package=flet_core",
        "--include-package=flet_runtime",
    ],
    "dearpygui": [
        "--include-package=dearpygui",
    ],
    "textual": [
        "--include-package=textual",
    ],
    "pygame": [
        "--include-package=pygame",
    ],
    "pyglet": [
        "--include-package=pyglet",
    ],
    "toga": [
        "--include-package=toga",
    ],
    "eel": [
        "--include-package=eel",
    ],
    "customtkinter": [
        "--include-package=customtkinter",
        "--enable-plugin=tk-inter",
    ],
    "pysimplegui": [
        "--include-package=PySimpleGUI",
    ],
}

# Nuitka 有官方插件的框架映射
# key: 框架检测名（小写）, value: Nuitka --enable-plugin 的参数值
NUITKA_OFFICIAL_PLUGINS: Dict[str, str] = {
    "pyqt6": "pyqt6",
    "pyqt5": "pyqt5",
    "pyside6": "pyside6",
    "pyside2": "pyside2",
    "tkinter": "tk-inter",
    "customtkinter": "tk-inter",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "multiprocessing": "multiprocessing",
}

# 已知的打包/构建/代码分析工具（不应作为项目依赖打包进 exe）
# 这些工具在依赖分析、隐藏导入生成、排除模块、依赖安装等阶段全部过滤
BUILD_DEV_TOOLS: frozenset[str] = frozenset({
    "pyinstaller", "nuitka", "cx_freeze", "py2exe",
    "black", "mypy", "bandit", "pylint", "flake8",
    "pyarmor", "safety", "coverage", "pytest",
    "isort", "ruff", "pre_commit", "tox", "nox",
    "sphinx", "mkdocs", "pdoc",
})

# 跨平台库在非当前平台上不需要的后端模块（按需打包，减小 exe 体积）
# 库会按平台动态加载对应后端，Windows 打包时排除 Linux/macOS/BSD 等后端。
# 来源：各库官方源码的平台后端命名约定
# 格式: "库名": { "win32": [当前平台需保留], "exclude_on_win32": [Windows 上排除] }
PLATFORM_SPECIFIC_MODULES: Dict[str, Dict[str, List[str]]] = {
    # psutil 来源: https://github.com/giampaolo/psutil
    "psutil": {
        "exclude_on_win32": [
            "psutil._pslinux",
            "psutil._psosx",
            "psutil._psbsd",
            "psutil._pssunos",
            "psutil._psaix",
            "psutil._psposix",
        ],
    },
}

# 所有 Qt 绑定包列表（用于冲突检测）
QT_BINDINGS: Set[str] = {"PyQt6", "PyQt5", "PySide6", "PySide2"}

# 已配置的库列表（加速缓存）
#
# 作用：打包工具在分析子模块时，优先使用此列表中的已知配置（快速路径），
#       跳过 `pip show` 动态查询。不在此列表中的库仍可通过自动分析正常处理，
#       只是会产生一次 `pip show` 调用。
#
# 维护原则：
#   - 标准库 → 已在 STDLIB_MODULES 中，不需要在此重复
#   - 第三方库 → 仅添加 PyPI 上广泛使用的库（数千+ stars / 每月百万+下载量）
#   - 来源：各库的 PyPI 官方页面 (https://pypi.org/project/<name>/) 和官方文档
#   - 不在此列表的第三方库：自动分析路径 `pip show -f` + AST import 扫描
CONFIGURED_LIBRARIES: Set[str] = {
    # GUI框架
    "PyQt6",
    "PyQt5",
    "PySide6",
    "PySide2",
    "tkinter",
    "customtkinter",
    "wx",
    "wxPython",
    "kivy",
    "flet",
    "dearpygui",
    "DearPyGui",
    "toga",
    "textual",
    "PySimpleGUI",
    "PySimpleGUIQt",
    "PySimpleGUIWx",
    "eel",
    "pyforms",
    "GUI",
    "pygui",
    "libavg",
    "wax",
    # Web爬虫
    "selenium",
    "scrapy",
    "Scrapy",
    "playwright",
    "requests_html",
    "bs4",
    "beautifulsoup4",
    "lxml",
    # Web框架
    "flask",
    "Flask",
    "django",
    "Django",
    "fastapi",
    "tornado",
    "aiohttp",
    "gradio",
    "streamlit",
    "dash",
    "bokeh",
    "altair",
    # 数据科学
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "seaborn",
    "plotly",
    "statsmodels",
    # 机器学习
    "sklearn",
    "scikit-learn",
    "tensorflow",
    "tf",
    "torch",
    "pytorch",
    "transformers",
    "xgboost",
    "lightgbm",
    "catboost",
    "onnxruntime",
    # 数据库
    "pymongo",
    "redis",
    "pymysql",
    "psycopg2",
    "sqlalchemy",
    "SQLAlchemy",
    "sqlmodel",
    "alembic",
    "peewee",
    "motor",
    "aiomysql",
    "aiopg",
    # 办公文档
    "openpyxl",
    "xlrd",
    "xlwt",
    "docx",
    "python-docx",
    "pptx",
    "python-pptx",
    "PyPDF2",
    "pypdf",
    "pdfplumber",
    "fitz",
    "pymupdf",
    "reportlab",
    # 任务调度
    "celery",
    "Celery",
    "apscheduler",
    "schedule",
    # 实用工具
    "requests",
    "httpx",
    "loguru",
    "tqdm",
    "click",
    "typer",
    "colorama",
    "arrow",
    "pendulum",
    "jieba",
    "qrcode",
    "pyqrcode",
    "barcode",
    "python-barcode",
    "watchdog",
    "dotenv",
    "python-dotenv",
    "pydantic",
    "marshmallow",
    "tenacity",
    "retrying",
    "faker",
    "Faker",
    "attrs",
    "attr",
    # 网络
    "websocket",
    "websocket-client",
    "paramiko",
    "sshtunnel",
    "httptools",
    "uvloop",
    "gunicorn",
    "urllib3",
    "dns",
    "dnspython",
    "httplib2",
    "aiohttp",
    "certifi",
    "chardet",
    "charset_normalizer",
    "idna",
    # 图像
    "PIL",
    "Pillow",
    "pillow-simd",
    "cv2",
    "imageio",
    "pytesseract",
    "easyocr",
    # 音频
    "pygame",
    "pyglet",
    "arcade",
    "panda3d",
    "ursina",
    "sounddevice",
    "soundfile",
    "pyaudio",
    "pydub",
    # 系统交互 / 进程管理
    "psutil",
    "win32api",
    "win32com",
    "win32gui",
    "win32process",
    "pywin32",
    "pyautogui",
    "pynput",
    "keyboard",
    "mouse",
    "comtypes",
    "pythonnet",
    "clr",
    # 缓存序列化
    "joblib",
    "dill",
    "cloudpickle",
    "cachetools",
    "diskcache",
    # 日期时间
    "pytz",
    "dateutil",
    "python-dateutil",
    # Markdown
    "markdown",
    "mistune",
    # 加密
    "cryptography",
    "Crypto",
    "pycryptodome",
    # YAML/TOML
    "yaml",
    "pyyaml",
    "toml",
    "tomli",
    # 其他
    "magic",
    "python-magic",
}

# 包名到导入名的映射（处理 PyPI 安装名和 Python import 名不一致的情况）
#
# 来源：各库的 PyPI 官方页面 (https://pypi.org/project/<name>/) 和官方文档
# 格式: "pip install 名称": "import 名称"
PACKAGE_IMPORT_MAP: Dict[str, str] = {
    # pip install X → import Y
    "dnspython": "dns",
    "pillow": "PIL",
    "beautifulsoup4": "bs4",
    "pyyaml": "yaml",
    "python-dateutil": "dateutil",
    "opencv-python": "cv2",
    "opencv-contrib-python": "cv2",
    "python-docx": "docx",
    "python-pptx": "pptx",
    "scikit-learn": "sklearn",
    "scikit-image": "skimage",
    "pycryptodome": "Crypto",
    "pycryptodomex": "Cryptodome",
    "pymysql": "pymysql",
    "mysql-connector-python": "mysql.connector",
    "psycopg2-binary": "psycopg2",
    "pywin32": "win32api",
    "python-dotenv": "dotenv",
    "PyMuPDF": "fitz",
    "requests": "requests",
    "urllib3": "urllib3",
    "certifi": "certifi",
    "charset-normalizer": "charset_normalizer",
    "idna": "idna",
    "cffi": "cffi",
    "ruamel.yaml": "ruamel",
}

# 已知的单文件模块（明确不是包）
KNOWN_SINGLE_FILE_MODULES: Set[str] = {
    "img2pdf",
    "pyperclip",
    "keyboard",
    "mouse",
    "pynput",
    "colorama",
    "tqdm",
    "click",
}

# 已知的标准库包（明确是包）
KNOWN_STDLIB_PACKAGES: Set[str] = {
    "email",
    "http",
    "urllib",
    "xml",
    "json",
    "logging",
    "multiprocessing",
    "concurrent",
    "asyncio",
    "collections",
    "distutils",
    "unittest",
    "doctest",
    "pdb",
    "pydoc",
}
