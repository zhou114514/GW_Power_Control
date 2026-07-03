import json
import socket
import threading

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication

from .GPP电源控制 import GPPPower
from .MU_N电源控制 import MUNPower
from .长条电源控制 import LongPower
from .方形电源控制 import SquarePower
from .version_control import get_current_version


VERSION = get_current_version()
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10002
DEVICE_TYPE_PSW = "PSW"
DEVICE_TYPE_GPD = "GPD"
DEVICE_TYPE_GPP = "GPP"
DEVICE_TYPE_MU_N = "MU_N"

# 单条消息（含未完成消息缓冲）上限，防止异常/恶意客户端持续发送无分隔符数据撑爆内存
MAX_MESSAGE_SIZE = 64 * 1024
# 客户端 socket 读超时：让读循环周期性检查 self._running，从而能在停止服务时及时退出
CLIENT_SOCKET_TIMEOUT = 1.0


class TCPServer(QThread):
    """JSON over TCP server for remote power control."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        super(TCPServer, self).__init__()
        self.host = host
        self.port = int(port)
        self._running = False
        self._client_threads = []

    def stop(self):
        self._running = False
        self.requestInterruption()

    def run(self):
        print("启动 TCP 服务")
        print(f"监听地址: {self.host}:{self.port}")
        self._running = True

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            result = probe_socket.connect_ex((self.host, self.port))
            if result == 0:
                print(f"端口 {self.port} 已被占用")
                self._running = False
                return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.settimeout(0.5)

            while self._running and not self.isInterruptionRequested():
                try:
                    client_socket, addr = server_socket.accept()
                    print(f"收到连接: {addr}")
                    client_thread = threading.Thread(
                        target=self.handle_client_connection,
                        args=(client_socket,),
                        daemon=True,
                    )
                    client_thread.start()
                    # 记录客户端线程并清理已结束的，便于停止服务时统一等待退出
                    self._client_threads = [t for t in self._client_threads if t.is_alive()]
                    self._client_threads.append(client_thread)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        print(f"接受连接异常: {e}")

        self._running = False
        # 停止服务时，客户端读循环会因 self._running=False + recv 超时而退出，这里等待其结束
        for client_thread in list(self._client_threads):
            try:
                client_thread.join(timeout=2)
            except Exception:
                pass
        self._client_threads = []

    def handle_client_connection(self, client_socket):
        client_socket.settimeout(CLIENT_SOCKET_TIMEOUT)
        try:
            # 用字节缓冲累积，只对完整的一行（以 \n 分隔）做 decode，
            # 从而正确处理跨 recv 分片的多字节 UTF-8，避免半个字符导致解码报错丢数据
            buffer = b""
            while self._running:
                try:
                    raw = client_socket.recv(1024)
                except socket.timeout:
                    continue
                if not raw:
                    break

                buffer += raw
                if len(buffer) > MAX_MESSAGE_SIZE:
                    print("单条消息超过上限，断开连接")
                    self.send(client_socket, self.make_backpack(False, None, "Message too large"))
                    break

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    message = line.decode("utf-8", errors="ignore").strip()
                    if not message:
                        continue
                    print(f"收到数据: {message}")
                    self._handle_message(client_socket, message)
        except Exception as e:
            try:
                peer_name = client_socket.getpeername()
            except Exception:
                peer_name = "unknown"
            print(f"{peer_name} 连接异常: {e}")
        finally:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            client_socket.close()

    def _handle_message(self, client_socket, message):
        try:
            cmd = json.loads(message)
        except Exception as e:
            print(f"JSON 解析失败: {e}; 原始消息: {message!r}")
            self.send(client_socket, self.make_backpack(False, None, "Format error"))
            return
        if not isinstance(cmd, dict):
            self.send(client_socket, self.make_backpack(False, None, "Format error: expected JSON object"))
            return

        response = self.cmd_handler(cmd)
        self.send(client_socket, response)

    def send(self, client_socket, data):
        payload = data + "\n"
        try:
            client_socket.sendall(payload.encode("utf-8"))
        except Exception as e:
            print(f"发送数据异常: {e}")

    def _get_device_collection(self, device_type):
        normalized = str(device_type or DEVICE_TYPE_PSW).upper()
        if normalized == DEVICE_TYPE_PSW:
            return LongPower.get_instances()
        if normalized == DEVICE_TYPE_GPD:
            return SquarePower.get_instances()
        if normalized == DEVICE_TYPE_GPP:
            return GPPPower.get_instances()
        if normalized == DEVICE_TYPE_MU_N:
            return MUNPower.get_instances()
        raise ValueError(f"Unsupported device type: {device_type}")

    def _resolve_device(self, params):
        params = params or {}
        device_type = str(params.get("DeviceType", DEVICE_TYPE_PSW)).upper()
        devices = self._get_device_collection(device_type)

        if not devices:
            raise RuntimeError(f"No {device_type} device available")

        device_name = str(params.get("DeviceName", "")).strip()
        if device_name:
            for device in devices:
                if getattr(device, "name", "") == device_name:
                    return device_type, device
            raise RuntimeError(f"Device not found: {device_name}")

        try:
            device_index = int(params.get("DeviceIndex", 0))
        except Exception:
            raise RuntimeError("DeviceIndex must be an integer")

        if device_index < 0 or device_index >= len(devices):
            raise RuntimeError(f"DeviceIndex out of range: {device_index}")

        return device_type, devices[device_index]

    def _check(self, params):
        return self.make_backpack(True, VERSION, None)

    def _connect_device(self, params):
        _, device = self._resolve_device(params)
        result = device.invoke_tcp_connect()
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _power_on(self, params):
        _, device = self._resolve_device(params)
        result = device.invoke_tcp_power_on()
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _power_off(self, params):
        _, device = self._resolve_device(params)
        result = device.invoke_tcp_power_off()
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _current_value(self, params):
        device_type, device = self._resolve_device(params)

        if device_type in (DEVICE_TYPE_GPD, DEVICE_TYPE_GPP, DEVICE_TYPE_MU_N):
            result = device.invoke_tcp_get_value()
            if not result[0]:
                return self.make_backpack(False, None, result[1] if len(result) > 1 else None)

            snapshot = result[1]
            value = {}
            for channel, channel_value in snapshot.items():
                value[f"CH{channel}"] = {"Voltage": channel_value[0], "Current": channel_value[1]}
            return self.make_backpack(True, value, None)

        voltage, current = device.get_value()
        return self.make_backpack(True, {"Voltage": voltage, "Current": current}, None)

    def _down_deflection(self, params):
        _, device = self._resolve_device(params)
        if not isinstance(device, LongPower):
            return self.make_backpack(False, None, "DownDeflection only supports PSW")

        if "Con" not in (params or {}):
            return self.make_backpack(False, None, "Missing parameter: Con")

        if not device.isConnected:
            return self.make_backpack(False, None, "Serial port not connected")

        device.tcp_deflect.emit(params["Con"], False)
        return self.make_backpack(True, None, None)

    def _set_voltage(self, params):
        if not params or "Channel" not in params or "Voltage" not in params:
            return self.make_backpack(False, None, "Missing parameter: Channel or Voltage")

        try:
            channel = int(params["Channel"])
            voltage = float(params["Voltage"])
        except (TypeError, ValueError):
            return self.make_backpack(False, None, "Channel/Voltage must be numeric")
        _, device = self._resolve_device(params)
        result = device.invoke_tcp_set_voltage(channel, voltage)
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _set_current(self, params):
        if not params or "Channel" not in params or "Current" not in params:
            return self.make_backpack(False, None, "Missing parameter: Channel or Current")

        try:
            channel = int(params["Channel"])
            current = float(params["Current"])
        except (TypeError, ValueError):
            return self.make_backpack(False, None, "Channel/Current must be numeric")
        _, device = self._resolve_device(params)
        result = device.invoke_tcp_set_current(channel, current)
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _set_channel_output(self, params):
        _, device = self._resolve_device(params)
        device_type = str(params.get("DeviceType", "")).upper()
        if device_type != DEVICE_TYPE_MU_N:
            return self.make_backpack(False, None, "SetChannelOutput only supports MU_N")

        if not params or "Channel" not in params:
            return self.make_backpack(False, None, "Missing parameter: Channel")

        try:
            channel = int(params["Channel"])
        except (TypeError, ValueError):
            return self.make_backpack(False, None, "Channel must be numeric")
        enable = bool(params.get("Enable", True))
        result = device.invoke_tcp_set_channel_output(channel, enable)
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _list_devices(self, params):
        value = {
            DEVICE_TYPE_PSW: [
                {"Index": index, "Name": device.name, "Connected": device.isConnected}
                for index, device in enumerate(LongPower.get_instances())
            ],
            DEVICE_TYPE_GPD: [
                {"Index": index, "Name": device.name, "Connected": device.isConnected}
                for index, device in enumerate(SquarePower.get_instances())
            ],
            DEVICE_TYPE_GPP: [
                {"Index": index, "Name": device.name, "Connected": device.isConnected}
                for index, device in enumerate(GPPPower.get_instances())
            ],
            DEVICE_TYPE_MU_N: [
                {
                    "Index": index,
                    "Name": device.name,
                    "Connected": device.isConnected,
                    "Channels": device.channel_count,
                }
                for index, device in enumerate(MUNPower.get_instances())
            ],
        }
        return self.make_backpack(True, value, None)

    def cmd_handler(self, cmd_dict):
        try:
            opcode = cmd_dict.get("opcode")
            if not opcode:
                return self.make_backpack(False, None, "Missing opcode")

            params = cmd_dict.get("parameter", {})
            handlers = {
                "check": self._check,
                "ListDevices": self._list_devices,
                "ConnectDevice": self._connect_device,
                "PowerON": self._power_on,
                "PowerOFF": self._power_off,
                "CurrentValue": self._current_value,
                "DownDeflection": self._down_deflection,
                "SetVoltage": self._set_voltage,
                "SetCurrent": self._set_current,
                "SetChannelOutput": self._set_channel_output,
            }

            if opcode not in handlers:
                return self.make_backpack(False, None, f"Unknown command: {opcode}")

            return handlers[opcode](params)
        except Exception as e:
            return self.make_backpack(False, None, f"Command execution error: {e}")

    def make_backpack(self, is_success, value=None, msg=None):
        backpack = {
            "IsSuccessful": is_success,
            "Value": value if value is not None else "Null",
            "ErrorMessage": msg if msg is not None else "Null",
        }
        return json.dumps(backpack, ensure_ascii=False)


if __name__ == "__main__":
    app = QApplication([])
    server = TCPServer()
    server.start()
    app.exec_()
