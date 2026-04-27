# -*- coding: utf-8 -*-
"""
更新检测模块。

这个模块的职责是“判断是否存在新版本”，不负责界面展示，也不负责实际安装。

如果用 C++ 的分层思路来理解，它更像：

1. 一个纯业务层工具模块
2. 外加一个很薄的异步线程包装

模块主要分成两部分：

1. 纯函数部分
   - 路径标准化
   - 下载清单
   - 解析清单
   - 比较版本
2. Qt 线程部分
   - `UpdateCheckThread`
   - 用于避免 UI 线程阻塞
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import urllib.parse
import urllib.request

from PyQt5 import QtCore

from .version_control import parse_version_tuple


@dataclass(frozen=True)
class UpdateManifest:
    """
    更新清单数据对象。

    可以把它类比成下面这种 C++ 结构体：

    ```cpp
    struct UpdateManifest {
        std::string version;
        std::string download_url;
        std::string release_notes;
        bool force_update;
    };
    ```

    它只负责存储“远端清单里的数据”，不负责任何业务逻辑。
    """

    version: str
    download_url: str
    release_notes: str
    force_update: bool


@dataclass(frozen=True)
class UpdateCheckResult:
    """
    更新检测结果对象。

    它相当于一个统一的返回值封装，用来描述：

    - 检测是否成功
    - 是否存在新版本
    - 新版本号是多少
    - 下载地址是什么
    - 如果失败，错误信息是什么

    这种写法和 C++ 里常见的 Result / Response 对象思路一致。
    """

    success: bool
    has_update: bool
    latest_version: str = ""
    download_url: str = ""
    release_notes: str = ""
    error_message: str = ""
    force_update: bool = False


def _normalize_manifest_url(manifest_url: str) -> str:
    """
    把清单地址标准化成 `urlopen()` 可处理的形式。

    当前支持三类输入：

    1. Windows 本地绝对路径
       例如：`D:\\app\\update_manifest.json`
    2. 共享盘路径
       例如：`\\\\server\\share\\update_manifest.json`
    3. 标准 URL
       例如：`https://example.com/update_manifest.json`

    为什么要做这一步：

    - 上层调用者不必关心底层到底读的是文件还是 HTTP
    - 统一转成 urlopen 可以消费的格式

    对 C++ 开发者来说，这个函数相当于“输入适配层”。
    """

    manifest_url = (manifest_url or "").strip()
    if not manifest_url:
        return ""

    # Windows 盘符路径或 UNC 共享路径，统一转 file:// URI。
    if re.match(r"^[a-zA-Z]:[\\/]", manifest_url) or manifest_url.startswith("\\\\"):
        return Path(manifest_url).expanduser().resolve().as_uri()

    parsed = urllib.parse.urlparse(manifest_url)
    if parsed.scheme:
        return manifest_url

    # 剩余情况按本地相对路径处理。
    return Path(manifest_url).expanduser().resolve().as_uri()


def _read_manifest_text(manifest_url: str, timeout: int) -> str:
    """
    下载或读取更新清单文本。

    流程是：

    1. 先把输入地址标准化
    2. 再通过 `urllib.request.urlopen()` 统一读取
    3. 最后解码成字符串

    这里把本地文件和 HTTP 都走同一个读取接口，
    这样业务层就不需要写两套逻辑。
    """

    normalized_url = _normalize_manifest_url(manifest_url)
    if not normalized_url:
        raise ValueError("未配置更新清单地址")

    with urllib.request.urlopen(normalized_url, timeout=max(timeout, 1)) as response:
        charset = response.headers.get_content_charset() or "utf-8"

        # lstrip("\ufeff") 用来去掉 UTF-8 BOM。
        # 这是为了兼容部分工具生成的 JSON 文件头。
        return response.read().decode(charset).lstrip("\ufeff")


def _parse_manifest(manifest_text: str) -> UpdateManifest:
    """
    把 JSON 文本解析成 `UpdateManifest` 对象。

    这个函数做两件事：

    1. 验证 JSON 结构是否是字典
    2. 验证关键字段 `version` 是否存在

    如果清单缺少关键字段，会主动抛异常。
    这样调用方可以明确知道是“清单格式错误”，而不是误判成“没有更新”。
    """

    payload = json.loads(manifest_text)
    if not isinstance(payload, dict):
        raise ValueError("更新清单格式错误")

    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError("更新清单缺少 version")

    return UpdateManifest(
        version=version,
        download_url=str(payload.get("download_url") or "").strip(),
        release_notes=str(payload.get("release_notes") or "").strip(),
        force_update=bool(payload.get("force_update", False)),
    )


def check_for_updates(current_version: str, manifest_url: str, timeout: int = 3) -> UpdateCheckResult:
    """
    更新检测主入口。

    这是本模块最核心的业务函数。

    它的执行流程是：

    1. 读取更新清单文本
    2. 解析为 `UpdateManifest`
    3. 比较远端版本和本地版本
    4. 返回统一的 `UpdateCheckResult`

    版本比较的关键点：

    - 不是直接比字符串
    - 而是调用 `parse_version_tuple()`
    - 例如：
      - `v1.1.10` -> `(1, 1, 10, 0)`
      - `v1.1.4` -> `(1, 1, 4, 0)`

    这样比较结果才是正确的。
    """

    try:
        manifest = _parse_manifest(_read_manifest_text(manifest_url, timeout))
    except Exception as exc:
        return UpdateCheckResult(
            success=False,
            has_update=False,
            error_message=str(exc),
        )

    has_update = parse_version_tuple(manifest.version) > parse_version_tuple(current_version)
    return UpdateCheckResult(
        success=True,
        has_update=has_update,
        latest_version=manifest.version,
        download_url=manifest.download_url,
        release_notes=manifest.release_notes,
        force_update=manifest.force_update,
    )


class UpdateCheckThread(QtCore.QThread):
    """
    版本检测线程。

    为什么要单独起线程：

    - 更新清单可能来自本地文件、共享盘、HTTP
    - 读取它们都可能阻塞
    - 如果直接在主线程做，界面会卡住

    这个类的作用类似 C++/Qt 里把耗时任务丢到工作线程执行。

    `update_checked` 信号相当于“异步回调出口”。
    """

    update_checked = QtCore.pyqtSignal(object)

    def __init__(self, current_version: str, manifest_url: str, timeout: int = 3, parent=None):
        """
        构造线程对象。

        参数含义：

        - `current_version`：当前本地版本
        - `manifest_url`：更新清单地址
        - `timeout`：读取清单超时时间
        - `parent`：Qt 父对象
        """

        super(UpdateCheckThread, self).__init__(parent)
        self.current_version = current_version
        self.manifest_url = manifest_url
        self.timeout = timeout

    def run(self):
        """
        线程入口函数。

        Qt 中 `QThread.start()` 最终会异步调用这里。
        它相当于 C++ 线程函数的入口点。
        """

        result = check_for_updates(self.current_version, self.manifest_url, self.timeout)
        self.update_checked.emit(result)
