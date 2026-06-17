# 光学头电源控制 — TCP 远程控制协议

| 项目 | 说明 |
|------|------|
| 协议版本 | v1.1（对应软件 v1.1.2+） |
| 传输层 | TCP |
| 编码 | UTF-8 |
| 消息格式 | JSON，以换行符 `\n` 作为帧分隔符 |
| 实现模块 | `Projects/电源控制/TCPServer.py` |
| 适用设备 | 长条电源（`type: long`），方形电源暂不支持远程控制 |

---

## 1. 概述

本协议用于上位机测试软件与**光学头电源控制**程序之间的远程通信。客户端通过 TCP 连接发送 JSON 命令，服务端解析后控制指定电源设备（串口连接、输出开关、读数、电压拉偏等），并以 JSON 响应返回执行结果。

### 1.1 通信模型

```
┌─────────────┐    TCP (JSON + \n)    ┌──────────────────────────┐
│  远程客户端  │ ◄──────────────────► │  光学头电源控制软件       │
│ (测试终端等) │                       │  TCPServer → 长条电源实例 │
└─────────────┘                       └──────────────────────────┘
```

- **请求-响应模式**：每条命令对应一条响应，客户端应等待响应后再发送下一条（推荐）。
- **多客户端**：服务端为每个连接创建独立线程，可并发接入多个客户端。
- **长连接**：连接保持至客户端断开；服务端在连接关闭时释放资源。

### 1.2 服务端配置

软件启动时通过 `TCPServer.from_config()` 读取项目根目录下的 `Auto_config.ini`：

```ini
[TCP]
ip = 127.0.0.1
port = 10002
auto_connect = True
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ip` | `127.0.0.1` | 日志中显示的本机地址；实际 `bind` 为 `0.0.0.0`（所有网卡） |
| `port` | `10002` | TCP 监听端口 |
| `auto_connect` | `True` | `True` 时软件启动后自动开启 TCP 服务；`False` 时不监听 |

修改 `[TCP]` 配置后需**重启软件**生效。启动日志会打印 `本机IP地址` 与 `端口号`，客户端应连接 `ip:port`。

---

## 2. 帧格式

### 2.1 请求帧

每条请求为**一行** UTF-8 JSON 字符串，以 `\n`（`0x0A`）结尾。

```json
{
  "opcode": "<命令名>",
  "parameter": { }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `opcode` | string | 是 | 命令操作码，区分大小写 |
| `parameter` | object | 否 | 命令参数；无参数时可省略或传 `{}` |

**示例（单行发送）**：

```json
{"opcode":"check"}
```

```json
{"opcode":"PowerON","parameter":{"device":"GXT"}}
```

### 2.2 响应帧

每条响应同样为**一行** UTF-8 JSON 字符串，以 `\n` 结尾。

```json
{
  "IsSuccessful": true,
  "Value": "Null",
  "ErrorMessage": "Null"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `IsSuccessful` | boolean | `true` 表示命令执行成功；`false` 表示失败 |
| `Value` | any | 成功时的返回值；无返回值时为字符串 `"Null"` |
| `ErrorMessage` | string | 失败时的错误描述；成功时为字符串 `"Null"` |

### 2.3 粘包与分包处理

- 接收端应使用缓冲区累积数据，按 `\n` 切分后逐条 `json.loads` 解析。
- 单次 `recv` 可能包含多条完整消息，也可能只包含半条消息。
- JSON 解析失败时，服务端返回：

```json
{"IsSuccessful":false,"Value":"Null","ErrorMessage":"Format error"}
```

---

## 3. 设备标识（多电源场景）

当系统中配置了多个长条电源时，通过 `parameter` 中的 `device` 字段指定目标设备。

| 字段 | 类型 | 别名 | 说明 |
|------|------|------|------|
| `device` | string | `Device` | 设备 ID，对应 `power_config.json` 中 `devices[].id` |

**设备解析规则**：

1. 若 `parameter` 中提供了 `device` / `Device`：按 ID 查找对应长条电源实例。
2. 若未提供：使用第一个 `remote: true` 的长条电源作为默认设备。
3. 若仍无可用设备：返回 `No power control board available`。

**设备必须满足**：

- 在 `power_config.json` 中 `type` 为 `"long"`；
- `remote` 为 `true`（电源设置界面可配置）。

### 3.1 预设场景设备 ID 参考

| 场景 ID | 设备 ID | 名称 | 默认电压 | 默认电流 |
|---------|---------|------|----------|----------|
| `gxt_only` | `GXT` | 光学头电源 | 42.0 V | 3.5 A |
| `gxt_xw` | `GXT` | 光学头电源 | 42.0 V | 3.5 A |
| `gxt_xw` | `GF` | XW光放电源 | 5.4 V | 10.0 A |
| `gxt_fgw` | `GXT` | 光学头电源 | 42.0 V | 3.5 A |
| `gxt_fgw` | `GF` | FGW光放电源 | 4.4 V | 13.5 A |

---

## 4. 命令列表

### 4.1 总览

| opcode | 需要设备 | 说明 |
|--------|----------|------|
| `check` | 否 | 查询软件版本 |
| `ConnectDevice` | 是 | 打开串口连接电源 |
| `PowerON` | 是 | 上电（设置默认 V/I 并开启输出） |
| `PowerOFF` | 是 | 下电（关闭输出） |
| `CurrentValue` | 是 | 读取当前输出电压、电流 |
| `DownDeflection` | 是 | 电压拉偏测试 |

---

### 4.2 `check` — 版本查询

查询服务端软件版本，用于连通性检测与版本兼容判断。

**请求**

```json
{"opcode":"check"}
```

**成功响应**

```json
{
  "IsSuccessful": true,
  "Value": "v1.1.2",
  "ErrorMessage": "Null"
}
```

`Value` 为 `更新内容.csv` 最后一行的版本号字符串；无法读取时为 `"Unknown"`。

---

### 4.3 `ConnectDevice` — 连接串口

打开指定电源对应的串口。等效于界面「打开串口」按钮。

**请求**

```json
{
  "opcode": "ConnectDevice",
  "parameter": {
    "device": "GXT"
  }
}
```

**成功响应**

```json
{
  "IsSuccessful": true,
  "Value": "Null",
  "ErrorMessage": "Null"
}
```

**常见错误**

| ErrorMessage | 原因 |
|--------------|------|
| `Device not found: <id>` | 设备 ID 不存在 |
| `Device remote control disabled: <id>` | 该设备未启用远程控制 |
| `No power control board available` | 无长条电源实例 |
| 串口打开失败（空字符串或异常信息） | 串口被占用、端口号错误或设备未连接 |

---

### 4.4 `PowerON` — 上电

在串口已连接的前提下：发送预设电压/电流 → 启动数据采集 → 开启电源输出。等效于界面「开始输出」，但**不弹出确认对话框**。

**前置条件**：串口已连接（可先调用 `ConnectDevice`）。

**请求**

```json
{
  "opcode": "PowerON",
  "parameter": {
    "device": "GXT"
  }
}
```

**成功响应**

```json
{
  "IsSuccessful": true,
  "Value": "Null",
  "ErrorMessage": "Null"
}
```

**常见错误**

| ErrorMessage | 原因 |
|--------------|------|
| `Port not connected` | 串口未连接 |
| `Operation timed out` | 主线程调度超时（默认 30 s） |

**行为说明**

- 电压、电流取自 `power_config.json` 中该设备的 `default_voltage`、`default_current`。
- 上电后自动开始电压/电流采集，数据写入 `./电源采集数据/<设备名>_<时间戳>.csv`。

---

### 4.5 `PowerOFF` — 下电

关闭电源输出并停止采集。等效于界面「停止输出」（远程模式下不触发 FTP 上传）。

**请求**

```json
{
  "opcode": "PowerOFF",
  "parameter": {
    "device": "GXT"
  }
}
```

**成功响应**

```json
{
  "IsSuccessful": true,
  "Value": "Null",
  "ErrorMessage": "Null"
}
```

---

### 4.6 `CurrentValue` — 读取电压电流

返回电源当前**输出**电压与电流（来自采集线程缓存值 `CurrentV` / `CurrentI`）。

> 若未上电或未开启采集，返回值可能为 `0`。

**请求**

```json
{
  "opcode": "CurrentValue",
  "parameter": {
    "device": "GXT"
  }
}
```

**成功响应**

```json
{
  "IsSuccessful": true,
  "Value": {
    "Voltage": 42.0,
    "Current": 1.25
  },
  "ErrorMessage": "Null"
}
```

| Value 字段 | 类型 | 单位 | 说明 |
|------------|------|------|------|
| `Voltage` | number | V | 当前输出电压 |
| `Current` | number | A | 当前输出电流 |

---

### 4.7 `DownDeflection` — 电压拉偏

启动自动电压拉偏测试。等效于界面「降至 36V / 升至 45V / 回到 42V」按钮，远程模式下**不弹窗提示**。

**前置条件**：串口已连接。

**请求**

```json
{
  "opcode": "DownDeflection",
  "parameter": {
    "Con": "Lower",
    "device": "GXT"
  }
}
```

| 参数 | 类型 | 必填 | 取值 | 说明 |
|------|------|------|------|------|
| `Con` | string | 是 | 见下表 | 拉偏方向 |

**`Con` 取值**

| 值 | 含义 | 目标电压 |
|----|------|----------|
| `Lower` | 向下拉偏 | 36 V |
| `Higher` | 向上拉偏 | 45 V |
| `Normal` | 恢复默认 | 42 V |

**成功响应**

```json
{
  "IsSuccessful": true,
  "Value": "Null",
  "ErrorMessage": "Null"
}
```

> 拉偏为**异步过程**：命令返回成功仅表示拉偏任务已启动，实际电压变化以每秒约 0.1 V 步进，到达目标后自动停止。可通过周期性 `CurrentValue` 查询进度。

**常见错误**

| ErrorMessage | 原因 |
|--------------|------|
| `Missing parameter: Con` | 未提供 `Con` 参数 |
| `Serial port not connected` | 串口未连接 |

---

## 5. 通用错误码

除各命令特有错误外，以下为全局错误：

| ErrorMessage | 触发条件 |
|--------------|----------|
| `Missing opcode` | 请求 JSON 中无 `opcode` 字段 |
| `Unknown command: <opcode>` | 不支持的命令名 |
| `Format error` | JSON 格式非法 |
| `No power control board available` | 系统中无长条电源实例 |
| `Device not found: <id>` | 指定设备 ID 不存在 |
| `Device remote control disabled: <id>` | 设备 `remote` 为 `false` |
| `Command execution error: <detail>` | 服务端内部异常 |
| `Missing required field: <field>` | 参数字段缺失 |

---

## 6. 推荐调用流程

### 6.1 基本上下电

```
客户端                          服务端
  │                               │
  │──── TCP 连接 ────────────────►│
  │                               │
  │──── {"opcode":"check"} ──────►│
  │◄─── 版本响应 ─────────────────│
  │                               │
  │──── ConnectDevice ───────────►│  打开串口
  │◄─── 成功 ─────────────────────│
  │                               │
  │──── PowerON ─────────────────►│  上电 + 采集
  │◄─── 成功 ─────────────────────│
  │                               │
  │──── CurrentValue (可选) ─────►│  读电压电流
  │◄─── {Voltage, Current} ───────│
  │                               │
  │──── PowerOFF ────────────────►│  下电
  │◄─── 成功 ─────────────────────│
  │                               │
  │──── 断开连接 ─────────────────►│
```

### 6.2 拉偏测试

```
ConnectDevice → PowerON → DownDeflection(Con=Lower/Higher/Normal)
                         → 轮询 CurrentValue 直至电压稳定
                         → PowerOFF
```

---

## 7. 客户端示例

### 7.1 Python

```python
import json
import socket

HOST = "127.0.0.1"
PORT = 4070
DEVICE = "GXT"


def send_cmd(sock, opcode, parameter=None):
  req = {"opcode": opcode}
  if parameter is not None:
    req["parameter"] = parameter
  sock.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
  data = b""
  while b"\n" not in data:
    chunk = sock.recv(4096)
    if not chunk:
      raise ConnectionError("连接已关闭")
    data += chunk
  line, _ = data.split(b"\n", 1)
  return json.loads(line.decode("utf-8"))


with socket.create_connection((HOST, PORT), timeout=10) as sock:
  print(send_cmd(sock, "check"))
  print(send_cmd(sock, "ConnectDevice", {"device": DEVICE}))
  print(send_cmd(sock, "PowerON", {"device": DEVICE}))
  print(send_cmd(sock, "CurrentValue", {"device": DEVICE}))
  print(send_cmd(sock, "DownDeflection", {"device": DEVICE, "Con": "Lower"}))
  print(send_cmd(sock, "PowerOFF", {"device": DEVICE}))
```

### 7.2 命令行（PowerShell + netcat 替代）

可使用任意支持 TCP 的工具发送单行 JSON。例如用 Python 一行命令：

```powershell
python -c "import socket,json;s=socket.create_connection(('127.0.0.1',4070));s.sendall(b'{\"opcode\":\"check\"}\n');print(s.recv(4096).decode())"
```

---

## 8. 注意事项

1. **串口独占**：同一电源串口只能被一个进程占用；远程 `ConnectDevice` 前请确保串口未被其他程序打开。
2. **线程安全**：电源操作通过 Qt 主线程调度执行，单条命令最长等待 30 秒。
3. **采集依赖**：`CurrentValue` 返回的是采集线程缓存值；上电后建议等待约 1 秒再读取。
4. **拉偏异步**：`DownDeflection` 立即返回，实际拉偏在后台进行，需自行轮询电压。
5. **安全限流**：电流超过 `power_config.json` 中 `current_limit` 时，软件会自动停止采集并弹窗告警（本地界面）。
6. **配置生效**：修改 `power_config.json` 或 `Auto_config.ini` 后需重启软件；可通过 `check` 命令确认版本与连通性。

---

## 9. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | 首版：基于 TCPServer.py（v1.1.2）整理 JSON 远程控制协议 |
| v1.1 | 2026-06-09 | TCPServer 启动时读取 `Auto_config.ini`；移除旧版二进制协议 |
