# -*- coding: utf-8 -*-
"""
版本控制辅助模块。

这个文件只做三件事：

1. 读取当前程序版本信息：`version.json`
2. 读取版本更新记录：`更新内容.csv`
3. 生成界面可直接使用的版本说明 HTML

如果用 C++ 的思路来理解，这个模块更像一个“轻量级版本服务”：

- `VersionInfo` 相当于一个只存数据的 struct/class
- `load_version_info()` 相当于工厂函数，负责构造 `VersionInfo`
- 其他函数相当于这个“服务”的若干工具接口

模块本身没有保存运行时状态，所有函数都基于文件现读现算，
因此它比较接近“无状态工具模块”。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re

import pandas as pd


# 项目根目录。
# Path(__file__) 表示当前这个 Python 文件本身的路径。
# resolve() 会把它转成绝对路径。
# parents[2] 表示向上回溯两级目录：
# Projects/电源控制/version_control.py -> Projects/电源控制 -> Projects -> 项目根目录
ROOT_PATH = Path(__file__).resolve().parents[2]

# 当前版本信息文件。
VERSION_FILE_PATH = ROOT_PATH / "version.json"

# 更新记录文件。
CHANGELOG_FILE_PATH = ROOT_PATH / "更新内容.csv"


@dataclass(frozen=True)
class VersionInfo:
    """
    版本信息数据对象。

    对 C++ 开发者来说，可以把它理解成一个：

    ```cpp
    struct VersionInfo {
        std::string app_name;
        std::string display_version;
        int
        int minor; major;
        int patch;
        int build;
        std::string release_date;
        std::string channel;
    };
    ```

    `@dataclass` 的作用就是：自动帮你生成初始化函数等样板代码。
    `frozen=True` 表示对象创建后不可修改，类似“只读配置对象”。
    """

    app_name: str
    display_version: str
    major: int
    minor: int
    patch: int
    build: int
    release_date: str
    channel: str

    @property
    def semantic_version(self) -> str:
        """
        生成语义化版本号字符串，例如 `1.1.4`。

        `@property` 在 Python 里类似 C++ 的只读 getter：

        - Python 调用方式：`info.semantic_version`
        - 不需要写成：`info.semantic_version()`
        """

        return f"{self.major}.{self.minor}.{self.patch}"


def _read_version_payload() -> dict:
    """
    从 `version.json` 读取原始字典数据。

    返回值是 Python 的 `dict`，可以类比成：

    ```cpp
    std::unordered_map<std::string, JsonValue>
    ```

    这里不抛异常，而是统一在失败时返回空字典。
    这样上层逻辑可以继续走降级分支，而不是直接崩掉。
    """

    if not VERSION_FILE_PATH.exists():
        return {}

    try:
        with VERSION_FILE_PATH.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except Exception:
        return {}

    return payload if isinstance(payload, dict) else {}


def _read_changelog_dataframe() -> pd.DataFrame:
    """
    读取 `更新内容.csv`，返回 pandas 的 DataFrame。

    如果你熟悉 C++，可以把 DataFrame 暂时理解成“二维表对象”：

    - 类似一个带列名的表
    - 每列有统一名字
    - 支持按列过滤、按行索引

    例如这里最终会形成两列：

    - `版本号`
    - `更新内容`

    失败时返回一个空表，而不是抛异常。
    """

    if not CHANGELOG_FILE_PATH.exists():
        return pd.DataFrame(columns=["版本号", "更新内容"])

    try:
        dataframe = pd.read_csv(
            str(CHANGELOG_FILE_PATH),
            header=None,
            names=["版本号", "更新内容"],
            encoding="utf-8-sig",
        ).fillna("")
    except Exception:
        return pd.DataFrame(columns=["版本号", "更新内容"])

    return dataframe


def _read_latest_changelog_version() -> str:
    """
    从更新记录里取最后一行版本号，作为回退版本。

    为什么需要这个函数：

    - 正常情况：版本号来自 `version.json`
    - 降级情况：如果 `version.json` 缺失或损坏，就退回到 `更新内容.csv` 的最后一行

    这相当于给版本系统加了一层兜底。
    """

    dataframe = _read_changelog_dataframe()
    if dataframe.empty:
        return "Unknown"

    version_value = dataframe.iloc[-1, 0]
    return str(version_value).strip() or "Unknown"


def _parse_version_parts(version_text: str) -> tuple[int, int, int, int]:
    """
    把版本字符串解析成可比较的数字元组。

    例如：

    - `v1.1.4` -> `(1, 1, 4, 0)`
    - `1.2.3.5` -> `(1, 2, 3, 5)`

    为什么不用直接比较字符串：

    - `"v1.10.0"` 和 `"v1.2.0"` 不能按字典序比较
    - 必须拆成整数后逐段比较

    这个函数就是在做“版本号正规化”。
    """

    match = re.search(r"(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?", version_text or "")
    if not match:
        return 0, 0, 0, 0

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    build = int(match.group(4) or 0)
    return major, minor, patch, build


def parse_version_tuple(version_text: str) -> tuple[int, int, int, int]:
    """
    对外暴露的版本解析接口。

    `_parse_version_parts()` 是内部实现，
    这个函数相当于公开 API。

    之所以保留这一层包装，是为了把“内部函数”和“对外函数”区分开。
    将来如果内部实现变了，对外接口可以不变。
    """

    return _parse_version_parts(version_text)


def _coerce_int(value, fallback: int) -> int:
    """
    尝试把输入转成 int，失败则返回 fallback。

    作用类似 C++ 里：

    ```cpp
    int value = try_parse(input) ? parsed : fallback;
    ```

    为什么需要它：

    - `version.json` 里的字段理论上应当是数字
    - 但文件可能被手工改坏
    - 因此这里统一做容错转换
    """

    try:
        return int(value)
    except Exception:
        return fallback


def load_version_info() -> VersionInfo:
    """
    构造并返回 `VersionInfo` 对象。

    这是这个文件里最核心的函数，可以把它理解成：

    - 先读取原始配置
    - 再做容错和回退
    - 最后组装成强类型对象返回

    流程如下：

    1. 先读 `version.json`
    2. 再读 `更新内容.csv` 的最后一行，作为备用版本号
    3. 确定最终显示版本 `display_version`
    4. 从版本字符串里解析出 major/minor/patch/build
    5. 用解析结果和配置结果共同构造 `VersionInfo`
    """

    payload = _read_version_payload()
    fallback_version = _read_latest_changelog_version()

    display_version = str(payload.get("display_version") or fallback_version).strip() or "Unknown"
    parsed_major, parsed_minor, parsed_patch, parsed_build = _parse_version_parts(display_version)

    return VersionInfo(
        app_name=str(payload.get("app_name") or "光学头电源控制"),
        display_version=display_version,
        major=_coerce_int(payload.get("major"), parsed_major),
        minor=_coerce_int(payload.get("minor"), parsed_minor),
        patch=_coerce_int(payload.get("patch"), parsed_patch),
        build=_coerce_int(payload.get("build"), parsed_build),
        release_date=str(payload.get("release_date") or ""),
        channel=str(payload.get("channel") or "release"),
    )


def get_current_version() -> str:
    """
    取得当前显示版本号。

    这个函数相当于一个“便捷接口”。
    如果调用者只关心当前版本字符串，而不关心完整 `VersionInfo`，
    直接调用它即可。
    """

    return load_version_info().display_version


def _build_html_table(dataframe: pd.DataFrame) -> str:
    """
    把 DataFrame 转成 HTML 表格字符串。

    这里返回的是纯字符串，不是 GUI 控件。
    上层界面拿到这个 HTML 后，会塞进 QTextEdit 里显示。
    """

    return dataframe.to_html(index=False, border=1)


def get_about_html() -> str:
    """
    生成“版本说明弹窗”使用的 HTML 内容。

    当前策略是：

    1. 读取 `更新内容.csv`
    2. 找出与当前版本完全匹配的那一行
    3. 如果找到了：
       只显示“当前版本更新内容”
    4. 如果没找到：
       退回显示全部历史记录

    这样做的好处是：

    - 用户更新到新版本后，点版本号能直接看到“这一版更新了什么”
    - 如果维护记录不完整，也不至于弹窗空白
    """

    dataframe = _read_changelog_dataframe()
    if dataframe.empty:
        return "<p>未找到更新记录文件</p>"

    current_version = get_current_version().strip().lower()
    current_rows = dataframe[dataframe["版本号"].astype(str).str.strip().str.lower() == current_version]

    if not current_rows.empty:
        html = "<h3>当前版本更新内容</h3>"
        html += _build_html_table(current_rows)
        return html

    html = "<h3>更新记录</h3>"
    html += _build_html_table(dataframe)
    return html
