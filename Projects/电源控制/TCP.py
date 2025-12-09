import sys
import socket
import struct
import threading
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from bitstring import *
import time

from .tool import *
from .方形电源控制 import SquarePower
from .长条电源控制 import LongPower

excel_name = Tool.init_execl_list()

class TCP():
    """TCP通信类"""
    name = 'TCP'
    portType="串口"
    Power_dict = {}

    res = socket.gethostbyname(socket.gethostname())

    def __init__(self, name):
        super(TCP, self).__init__()
        self.name = name
        self.IP = '127.0.0.1'
        self.Port = 4070
        self.auto_start()
        self.Power_dict_square = SquarePower.get_instances()
        # print(self.Power_dict_square)
        self.Power_dict_long = LongPower.get_instances()
        # print(self.Power_dict_long)
        self.excel = execl_file()
        # self.Power_dict[1].power_port_open()


    def auto_start(self):
        """自动启动"""
        cfg = Tool.read_config("TCP")
        if cfg["auto_connect"] == "True":
            self.IP = cfg["ip"]
            self.Port = int(cfg["port"])
            self.Open_callback()
            print(f"自动连接{self.IP}:{self.Port}成功")


    def send_data(self,client_socket, data):
        """发送数据"""
        client_socket.sendall(data)

    def handle_client_connection(self, client_socket):
        try:
            data = client_socket.recv(1024)
            if data:
                hex_data = [f'{byte:02X}' for byte in data]
                self.send_data(client_socket, data)

                # 解析数据
                type = hex_data[4] + hex_data[5]
                No = int(hex_data[6], 16) - 1  # 将编号转为整数并减去1以便索引
                command = hex_data[7] + hex_data[8]

                if command == "FE01":
                    self.control_power(type, No, hex_data[9])
                elif command == "FE02":
                    self.control_all_power(hex_data[9])
                elif command == "FE04":
                    self.set_voltage(type, No, hex_data)
                elif command == "FE05":
                    self.set_current(type, No, hex_data)
                elif command == "FE06":
                    self.save_data(type, No)
                elif command == "FE07":
                    self.save_all_power_data(hex_data[9])
                elif command == "FEA1":
                    self.start_record(hex_data[9])
                elif command == "FEA2":
                    self.stop_record(hex_data[9])

        except Exception as e:
            print(f"处理客户端连接时出错::{e}")
        finally:
            client_socket.close()

    # ========================================================================================
    # 以下为TCP命令处理函数

    def control_power(self, type, No, command):
        """控制单个电源的开启和关闭"""
        if type == "0101":
            power = self.Power_dict_square[No]
        elif type == "0102":
            power = self.Power_dict_long[No]
        else:
            print(f"未知电源类型: {type}")
            return

        if command == "01":
            power.output_open()
            # power.start_plot()
            print(f"{('方形电源' if type == '0101' else '长条电源')}{No + 1}打开")
        elif command == "00":
            power.output_close()
            # power.start_plot()
            print(f"{('方形电源' if type == '0101' else '长条电源')}{No + 1}关闭")

    def control_all_power(self, command):
        """控制所有电源的开启和关闭"""
        if command == "01":
            self.ALL_power_open()
            print("全部电源打开")
        elif command == "00":
            self.ALL_power_close()
            print("全部电源关闭")

    def set_voltage(self, type, No, hex_data):
        """设置电源电压"""
        if type == "0101":
            # 方形电源
            for i in range(1, 3):
                vol = ''.join(hex_data[9 + (i - 1) * 4: 9 + i * 4])  # 获取电压值
                vol_f = struct.unpack('!f', bytes.fromhex(vol))[0]
                self.Power_dict_square[No].V_set(i, vol_f)
                print(f"方形电源{No + 1}设置电压{vol_f}")
        elif type == "0102":
            # 长条电源
            vol = ''.join(hex_data[9:13])  # 获取电压值
            vol_f = struct.unpack('!f', bytes.fromhex(vol))[0]
            self.Power_dict_long[No].V_set(vol_f)
            print(f"长条电源{No + 1}设置电压{vol_f}")

    def set_current(self, type, No, hex_data):
        """设置电源电流"""
        if type == "0101":
            for i in range(1, 3):
                cur = ''.join(hex_data[9 + (i - 1) * 4: 9 + i * 4])  # 获取电流值
                cur_f = struct.unpack('!f', bytes.fromhex(cur))[0]
                self.Power_dict_square[No].I_set(i, cur_f)
                print(f"方形电源{No + 1}设置电流{cur_f}")
        elif type == "0102":
            cur = ''.join(hex_data[9:13])  # 获取电流值
            cur_f = struct.unpack('!f', bytes.fromhex(cur))[0]
            self.Power_dict_long[No].I_set(cur_f)
            print(f"长条电源{No + 1}设置电流{cur_f}")

    def save_data(self, type, No):
        """保存数据"""
        if type == "0101":
            power = self.Power_dict_square[No]
        elif type == "0102":
            power = self.Power_dict_long[0]
        else:
            print(f"未知电源类型: {type}")
            return

        if not power.checkplot():
            power.start_plot()
            # time.sleep(2)  # 这里的时间间隔可能需要根据实际情况调整

        self.excel.write_execl(power.save_data())
        print(f"{('方形电源' if type == '0101' else '长条电源')}{No + 1}保存数据")

    def save_all_power_data(self, command):
        """保存所有电源的数据"""
        directory = "./电源采集数据/"
        os.makedirs(directory, exist_ok=True)
        name = "性能测试前电流" if command == "01" else "性能测试后电流"
        
        self.start_all_plot()
        time.sleep(2)
        print(f"{name}保存数据")
        
        excel = execl_file()
        excel.read_execl(name)
        
        for i in range(len(self.Power_dict_square)):
            excel.write_execl(self.Power_dict_square[i].save_data())
        excel.write_execl(self.Power_dict_long[0].save_data())
        excel.save_execl(name)

    def start_record(self, excel_No):
        """开始记录数据"""
        self.start_all_plot()
        self.excel.read_execl(excel_name[excel_No])
        print(f"开始记录{excel_name[excel_No]}")

    def stop_record(self, excel_No):
        """停止记录数据"""
        self.excel.save_execl(excel_name[excel_No])
        print(f"停止记录")

    def start_all_plot(self):
        """开始所有电源的图形显示"""
        for i in range(len(self.Power_dict_square)):
            try:
                self.Power_dict_square[i].start_plot()
            except Exception as e:
                print(f"方形电源{i+1}图形显示异常:{e}")
        try:
            self.Power_dict_long[0].start_plot()
        except Exception as e:
            print(f"长条电源图形显示异常:{e}")

    def close_all_plot(self):
        """关闭所有电源的图形显示"""
        for i in range(len(self.Power_dict_square)):
            self.Power_dict_square[i].close_plot()
        self.Power_dict_long[0].close_plot()

    
    def ALL_power_open(self):
        """打开所有电源"""
        for i in range(len(self.Power_dict_square)):
            self.Power_dict_square[i].output_open()
        self.Power_dict_long[0].output_open()

    def ALL_power_close(self):
        """关闭所有电源"""
        self.Power_dict_long[0].output_close()
        for i in range(len(self.Power_dict_square)-1, -1, -1):
            self.Power_dict_square[i].output_close()

    # ========================================================================================
            

    def Open_callback(self):
        """打开TCP服务器"""
        tcp_thread = threading.Thread(target=self.start_tcp_server)
        tcp_thread.start()

    def start_tcp_server(self):
        """启动TCP服务器"""
        host = self.IP
        port = self.Port

        # 检查链接是否使用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex((host, port))
            if result == 0:
                print(f"端口{port}已被占用，请更换端口")
                return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((host, port))
            server_socket.listen(5)
            print(f"服务器正在{host}:{port}上监听...")

            while True:
                try:
                    client_socket, addr = server_socket.accept()
                    print(f"接受到来自{addr}的连接")

                    # 启动一个线程或进程来处理客户端连接，可扩展为多线程服务器
                    self.handle_client_connection(client_socket)
                except Exception as e:
                    print(f"连接异常:{e}")


    def close_tcp_server(self):
        """关闭TCP服务器"""
        pass
