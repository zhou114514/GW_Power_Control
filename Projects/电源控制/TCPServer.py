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

            while True:
                try:
                    client_socket, addr = server_socket.accept()
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
        result = self.LongPower[0].output_open_tcp()
        return self.make_backpack(result[0], None, result[1])
    
    def _handle_power_off(self, params):
        """处理关机命令"""
        result = self.LongPower[0].output_close_tcp()
        return self.make_backpack(result[0], None, result[1])
    
    def _handle_current_value(self, params):
        """处理获取电流电压命令"""
        voltage, current = self.LongPower[0].get_value()
        return self.make_backpack(True, {"Voltage": voltage, "Current": current}, None)
    
    def _handle_down_deflection(self, params):
        """处理下偏转命令"""
        if not params or "Con" not in params:
            return self.make_backpack(False, None, "Missing parameter: Con")
        
        deflection_type = params["Con"]
        
        self.LongPower[0].tcp_deflect.emit(deflection_type, False)
        return self.make_backpack(True, None, None)
    
    def _handle_connect_device(self, params):
        """处理连接设备命令"""
        result = self.LongPower[0].port_open()
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