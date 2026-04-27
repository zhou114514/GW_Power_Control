# -*- coding: utf-8 -*-
"""
更新安装执行器。

这个模块不负责“判断有没有更新”，只负责：

1. 生成外部更新脚本
2. 启动外部脚本
3. 让外部脚本在主程序退出后执行替换和重启

如果用 C++ 的思路类比，它相当于一个“安装器启动器”：

- Python 侧负责准备参数
- PowerShell 侧负责真正执行安装

为什么要设计成这样：

- Windows 下，正在运行的程序通常不能覆盖自己
- 所以必须由“外部进程”完成替换
"""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import uuid


def _ps_quote(value: str) -> str:
    """
    对 PowerShell 字符串做单引号转义。

    这是一个很小但很关键的辅助函数。
    它的作用类似 C++ 里给命令行参数做 escaping。

    例如：

    - 输入：`D:\\O'Reilly\\app.exe`
    - 输出：PowerShell 可安全使用的单引号字符串
    """

    return "'" + value.replace("'", "''") + "'"


def _build_powershell_script(
    target_pid: int,
    download_url: str,
    app_dir: str,
    executable_path: str,
    python_path: str,
    script_path: str,
    is_frozen: bool,
) -> str:
    """
    动态拼装外部更新用的 PowerShell 脚本。

    这个函数返回的不是“执行结果”，而是一整段脚本文本。

    可以把它类比成：

    - C++ 里先生成一个临时 `.bat` / `.ps1`
    - 然后再启动这个脚本

    为什么不用 Python 直接替换文件：

    - 因为当前 Python 进程本身就是主程序
    - 主程序退出前，自己的文件可能仍被占用
    - 所以必须把更新任务交给另一个独立进程
    """

    return f"""$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework

$targetPid = {target_pid}
$downloadUrl = {_ps_quote(download_url)}
$appDir = {_ps_quote(app_dir)}
$executablePath = {_ps_quote(executable_path)}
$pythonPath = {_ps_quote(python_path)}
$scriptPath = {_ps_quote(script_path)}
$isFrozen = ${str(bool(is_frozen)).lower()}

function Show-ErrorDialog([string]$message) {{
    [System.Windows.MessageBox]::Show($message, '软件更新失败') | Out-Null
}}

function Get-PackagePath([string]$sourceUrl, [string]$workDir) {{
    $fileName = ''
    if ($sourceUrl.StartsWith('http://') -or $sourceUrl.StartsWith('https://') -or $sourceUrl.StartsWith('file://')) {{
        $uri = [System.Uri]$sourceUrl
        $fileName = [System.IO.Path]::GetFileName($uri.LocalPath)
        if ([string]::IsNullOrWhiteSpace($fileName)) {{
            $fileName = 'update_package'
        }}
        $packagePath = Join-Path $workDir $fileName
        Invoke-WebRequest -Uri $sourceUrl -OutFile $packagePath -UseBasicParsing
        return $packagePath
    }}

    if (-not (Test-Path -LiteralPath $sourceUrl)) {{
        throw "未找到更新包：$sourceUrl"
    }}

    $fileName = [System.IO.Path]::GetFileName($sourceUrl)
    $packagePath = Join-Path $workDir $fileName
    Copy-Item -LiteralPath $sourceUrl -Destination $packagePath -Force
    return $packagePath
}}

try {{
    # 等待主程序退出。
    # 这里轮询目标进程是否还存在，最多等约 120 秒。
    for ($i = 0; $i -lt 240; $i++) {{
        if (-not (Get-Process -Id $targetPid -ErrorAction SilentlyContinue)) {{
            break
        }}
        Start-Sleep -Milliseconds 500
    }}

    if (Get-Process -Id $targetPid -ErrorAction SilentlyContinue) {{
        throw '主程序未退出，无法执行更新'
    }}

    $workDir = Join-Path ([System.IO.Path]::GetTempPath()) ('gw-power-update-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null

    try {{
        $packagePath = Get-PackagePath $downloadUrl $workDir
        $extension = [System.IO.Path]::GetExtension($packagePath).ToLowerInvariant()

        if ($extension -eq '.zip') {{
            # zip 包更新逻辑：
            # 1. 解压
            # 2. 如果 zip 最外层只有一个目录，则进入该目录
            # 3. 把内容覆盖到程序目录
            $extractDir = Join-Path $workDir 'extract'
            Expand-Archive -LiteralPath $packagePath -DestinationPath $extractDir -Force
            $children = @(Get-ChildItem -LiteralPath $extractDir -Force)
            $copyRoot = $extractDir
            if ($children.Count -eq 1 -and $children[0].PSIsContainer) {{
                $copyRoot = $children[0].FullName
            }}
            Get-ChildItem -LiteralPath $copyRoot -Force | ForEach-Object {{
                Copy-Item -LiteralPath $_.FullName -Destination $appDir -Recurse -Force
            }}
        }}
        elseif ($extension -eq '.exe') {{
            # exe 包更新逻辑：
            # 只适用于打包后的单文件程序。
            if (-not $isFrozen) {{
                throw '源码模式不支持直接替换 exe 更新包'
            }}
            Copy-Item -LiteralPath $packagePath -Destination $executablePath -Force
        }}
        else {{
            throw "不支持的更新包类型：$extension"
        }}
    }}
    finally {{
        # 无论成功还是失败，都尽量清理临时目录。
        Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }}

    # 更新完成后重启程序。
    if ($isFrozen) {{
        Start-Process -FilePath $executablePath -WorkingDirectory $appDir
    }}
    else {{
        Start-Process -FilePath $pythonPath -ArgumentList @($scriptPath) -WorkingDirectory $appDir
    }}
}}
catch {{
    Show-ErrorDialog($_.Exception.Message)
    exit 1
}}
"""


def launch_update_installer(download_url: str) -> None:
    """
    启动外部更新器。

    这是本模块对外暴露的主入口。

    这里完成的工作是：

    1. 计算当前程序路径
    2. 判断当前是源码模式还是打包模式
    3. 调用 `_build_powershell_script()` 生成脚本内容
    4. 把脚本写到临时目录
    5. 用独立 PowerShell 进程运行它

    对 C++ 开发者来说，这个函数可以理解成：

    - 先生成安装参数
    - 再 fork / spawn 一个独立安装器进程
    """

    # app_dir：程序目录
    # frozen 模式下取 exe 所在目录，源码模式下取入口脚本所在目录。
    app_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]))

    # executable_path：当前实际运行对象。
    # frozen 时是 exe，源码模式下是当前脚本路径。
    executable_path = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])

    # python_path：源码模式重启时使用的 Python 解释器路径。
    python_path = os.path.abspath(sys.executable)

    # script_path：源码模式重启时重新运行的主脚本。
    script_path = os.path.abspath(sys.argv[0])

    script_content = _build_powershell_script(
        target_pid=os.getpid(),
        download_url=download_url,
        app_dir=app_dir,
        executable_path=executable_path,
        python_path=python_path,
        script_path=script_path,
        is_frozen=getattr(sys, "frozen", False),
    )

    # 每次更新都生成唯一脚本文件，避免多次更新冲突。
    script_file = Path(tempfile.gettempdir()) / f"gw_power_update_{uuid.uuid4().hex}.ps1"
    script_file.write_text(script_content, encoding="utf-8-sig")

    # CREATE_NO_WINDOW 用于隐藏 PowerShell 黑窗口。
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_file),
        ],
        creationflags=creationflags,
        close_fds=True,
    )
