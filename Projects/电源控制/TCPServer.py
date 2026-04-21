<<<<<<< HEAD
import sys
import socket
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QLineEdit, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import threading

from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import socket
import time
import pandas as pd
import os
import datetime
import json

from .长条电源控制 import LongPower

# log_path = "C:\\Logs\\starer_sever"

VERSION = "Unknown" if pd.read_csv("./更新内容.csv", header=None, index_col=None).iloc[-1, 0] is None \
    else pd.read_csv("./更新内容.csv", header=None, index_col=None).iloc[-1, 0]

class TCPServer(QThread):
    """TCP服务器"""

    def __init__(self, host='127.0.0.1', port=10002):
        super(TCPServer, self).__init__()
        # 本机IP地址
        self.host = host
        self.port = int(port)
        self.LongPower: dict[str, LongPower] = LongPower.get_instances()

    def handle_client_connection(self, client_socket):
        """处理客户端连接"""
        try:
            buffer = ""
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                print(f"接收到来自{client_socket.getpeername()}的数据: {data}")
                if not data:
                    break
                buffer += data
                if "\n" in buffer:
                    messages = buffer.split("\n")
                    for message in messages[:-1]:
                        try: 
                            message = json.loads(message)
                            backpack = self.cmd_handler(message)
                            self.send(client_socket, backpack)
                        except:
                            print("命令格式错误")
                            self.send(client_socket, self.make_backpack(False, "Null", "Format error"))
                    buffer = messages[-1]
            if buffer:
                messages = buffer.split("\n")
                for message in messages[:-1]:
                    try: 
                        message = json.loads(message)
                        backpack = self.cmd_handler(message)
                        self.send(client_socket, backpack)
                    except:
                        print("命令格式错误")
                        self.send(client_socket, self.make_backpack(False, "Null", "Format error"))
        except Exception as e:
            print(f"{client_socket.getpeername()}:客户端连接异常: {e}")
        finally:
            print(f"关闭来自{client_socket.getpeername()}的连接")
            # self.client_threads.pop(client_socket.getpeername())  # 删除客户端线程
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()

    def run(self):
        """启动TCP服务器"""
        print("启动TCP服务器")
        print(f"本机IP地址: {self.host}")
        print(f"端口号: {self.port}")

        # 检查链接是否使用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex((self.host, self.port))
            if result == 0:
                print(f"端口{self.port}已被占用，请更换端口")
                return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind(('', self.port))
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.listen(5)
            print(f"服务器正在{self.host}:{self.port}上监听...")
=======
import json
import socket
import threading

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication

from .GPP电源控制 import GPPPower
from .长条电源控制 import LongPower
from .version_control import get_current_version


VERSION = get_current_version()
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10002
DEVICE_TYPE_PSW = "PSW"
DEVICE_TYPE_GPP = "GPP"


class TCPServer(QThread):
    """JSON over TCP server for remote power control."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        super(TCPServer, self).__init__()
        self.host = host
        self.port = int(port)

    def run(self):
        print("启动 TCP 服务")
        print(f"监听地址: {self.host}:{self.port}")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            result = probe_socket.connect_ex((self.host, self.port))
            if result == 0:
                print(f"端口 {self.port} 已被占用")
                return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
>>>>>>> 3e78017 (initial commit)

            while True:
                try:
                    client_socket, addr = server_socket.accept()
<<<<<<< HEAD
                    # self.clients[addr[0]] = client_socket
                    print(f"接受到来自{addr}的连接")
                    # 为每个客户端连接创建一个单独的线程来处理
                    client_thread = threading.Thread(target=self.handle_client_connection, args=(client_socket,))
                    # self.client_threads[addr] = client_thread
                    client_thread.start()
                    # print(self.client_threads)
                except Exception as e:
                    print(f"连接异常: {e}")

    def send(self, client_socket, data):
        """向客户端发送数据"""
        data = data + "\n"
        try:
            client_socket.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"向{client_socket.getpeername()}发送数据异常: {e}")

    def close_tcp_server(self):
        """关闭TCP服务器"""
        # 这里需要实现一个优雅的关闭机制，考虑到多线程情况
        pass


    def _check_device_available(self):
        """检查设备是否可用"""
        return len(self.LongPower) > 0
    
    def _handle_power_on(self, params):
        """处理开机命令"""
        result = self.LongPower[0].invoke_tcp_power_on()
        return self.make_backpack(result[0], None, result[1])
    
    def _handle_power_off(self, params):
        """处理关机命令"""
        result = self.LongPower[0].invoke_tcp_power_off()
        return self.make_backpack(result[0], None, result[1])
    
    def _handle_current_value(self, params):
        """处理获取电流电压命令"""
        voltage, current = self.LongPower[0].get_value()
        return self.make_backpack(True, {"Voltage": voltage, "Current": current}, None)
    
    def _handle_down_deflection(self, params):
        """处理下偏转命令"""
        if not params or "Con" not in params:
            return self.make_backpack(False, None, "Missing parameter: Con")
        
        if not self.LongPower[0].isConnected:
            return self.make_backpack(False, None, "Serial port not connected")
        
        deflection_type = params["Con"]
        
        self.LongPower[0].tcp_deflect.emit(deflection_type, False)
        return self.make_backpack(True, None, None)
    
    def _handle_connect_device(self, params):
        """处理连接设备命令"""
        result = self.LongPower[0].invoke_tcp_connect()
        return self.make_backpack(result[0], None, result[1])
    
    def _handle_check(self, params):
        """处理版本检查命令"""
        return self.make_backpack(True, VERSION, None)

    def cmd_handler(self, cmd_dict):
        """命令处理中心"""
        try:
            opcode = cmd_dict.get('opcode')
            if not opcode:
                return self.make_backpack(False, None, "Missing opcode")
            
            # 命令映射表 - 不需要设备的命令
            no_device_commands = {
                'check': self._handle_check
            }
            
            # 命令映射表 - 需要设备的命令
            device_commands = {
                'PowerON': self._handle_power_on,
                'PowerOFF': self._handle_power_off,
                'CurrentValue': self._handle_current_value,
                'DownDeflection': self._handle_down_deflection,
                'ConnectDevice': self._handle_connect_device
            }
            
            # 处理不需要设备的命令
            if opcode in no_device_commands:
                return no_device_commands[opcode](None)
            
            # 处理需要设备的命令
            if opcode in device_commands:
                # 检查设备是否可用
                if not self._check_device_available():
                    return self.make_backpack(False, None, "No power control board available")
                
                params = cmd_dict.get('parameter', {})
                return device_commands[opcode](params)
            
            # 未知命令
            return self.make_backpack(False, None, f"Unknown command: {opcode}")
            
        except KeyError as e:
            return self.make_backpack(False, None, f"Missing required field: {str(e)}")
        except Exception as e:
            return self.make_backpack(False, None, f"Command execution error: {str(e)}")

    def make_backpack(self, isSuccess: bool, value: dict | str | None = None, msg: str | None = None):
        """构造返回数据包
        
        Args:
            isSuccess: 命令是否执行成功
            value: 返回值，可以是字典、字符串或None
            msg: 错误消息，None时会转换为"Null"
        
        Returns:
            JSON格式的响应字符串
        """
        backpack = {
            "IsSuccessful": isSuccess,
            "Value": value if value is not None else "Null",
            "ErrorMessage": msg if msg is not None else "Null"
        }
        return json.dumps(backpack, ensure_ascii=False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    server = TCPServer()
    server.start()
    sys.exit(app.exec_())
=======
                    print(f"收到连接: {addr}")
                    client_thread = threading.Thread(
                        target=self.handle_client_connection,
                        args=(client_socket,),
                        daemon=True,
                    )
                    client_thread.start()
                except Exception as e:
                    print(f"接受连接异常: {e}")

    def handle_client_connection(self, client_socket):
        try:
            buffer = ""
            while True:
                raw = client_socket.recv(1024)
                if not raw:
                    break

                chunk = raw.decode("utf-8")
                print(f"收到数据: {chunk}")
                buffer += chunk

                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    if not message.strip():
                        continue
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
        except Exception:
            self.send(client_socket, self.make_backpack(False, None, "Format error"))
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
        if normalized == DEVICE_TYPE_GPP:
            return GPPPower.get_instances()
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

        if device_type == DEVICE_TYPE_GPP:
            result = device.invoke_tcp_get_value()
            if not result[0]:
                return self.make_backpack(False, None, result[1] if len(result) > 1 else None)

            snapshot = result[1]
            value = {
                "CH1": {"Voltage": snapshot[1][0], "Current": snapshot[1][1]},
                "CH2": {"Voltage": snapshot[2][0], "Current": snapshot[2][1]},
                "CH3": {"Voltage": snapshot[3][0], "Current": snapshot[3][1]},
            }
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

        _, device = self._resolve_device(params)
        channel = int(params["Channel"])
        voltage = float(params["Voltage"])
        result = device.invoke_tcp_set_voltage(channel, voltage)
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _set_current(self, params):
        if not params or "Channel" not in params or "Current" not in params:
            return self.make_backpack(False, None, "Missing parameter: Channel or Current")

        _, device = self._resolve_device(params)
        channel = int(params["Channel"])
        current = float(params["Current"])
        result = device.invoke_tcp_set_current(channel, current)
        return self.make_backpack(result[0], None, result[1] if len(result) > 1 else None)

    def _list_devices(self, params):
        value = {
            DEVICE_TYPE_PSW: [
                {"Index": index, "Name": device.name, "Connected": device.isConnected}
                for index, device in enumerate(LongPower.get_instances())
            ],
            DEVICE_TYPE_GPP: [
                {"Index": index, "Name": device.name, "Connected": device.isConnected}
                for index, device in enumerate(GPPPower.get_instances())
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
>>>>>>> 3e78017 (initial commit)
