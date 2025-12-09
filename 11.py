# from bitstring import *
# import pandas as pd
# import datetime
# from Projects.蓝转台.tool import *

# class Counter:
#     instances = []  # 存储所有Counter实例
#     total_count = 0  # 所有实例的总计数
    
#     def __init__(self):
#         self.count = 0  # 每个实例的计数
#         Counter.instances.append(self)  # 将实例添加到类属性列表中
    
#     def increment(self):
#         self.count += 1
#         Counter.total_count += 1  # 增加总计数
        
#     def decrement(self):
#         if self.count > 0:
#             self.count -= 1
#             Counter.total_count -= 1  # 减少总计数
        
#     @classmethod
#     def get_total_count(cls):
#         return cls.total_count  # 返回所有实例的总计数

#     @classmethod
#     def get_instance_counts(cls):
#         return [instance.count for instance in cls.instances]  # 返回所有实例的计数


# def test():
#     point = '2024-10-12 19:02:52'
#     df = pd.read_csv(f"./电源采集数据/方形电源1.txt", sep='\t', names=['时间', 'CH1', 'CH2'], index_col=0, encoding='utf-8')
#     df = df.loc[df.index.str.contains(point)]
#     df.to_csv(f"./电源采集数据/方形电源1_{point}.txt", sep='\t', index=True)


# def get_point():
#     now = datetime.datetime.now()
#     print(now)
#     point = now - datetime.timedelta(seconds=2)
#     print(point)
#     return point.strftime('%Y-%m-%d %H:%M:%S.%f')[:-7]


# import openpyxl

# # # 打开一个已存在的 Excel 文件
# # input_file = 'input.xlsx'
# # workbook = openpyxl.load_workbook(input_file)
# # # 选择活动工作表
# # sheet = workbook.active

# # # 要填充的数据，每行多个数据（假设填充三列）
# # data_to_fill = [
# #     ['数据1-1', '数据1-2', '数据1-3'],
# #     ['数据2-1', '数据2-2', '数据2-3'],
# #     ['数据3-1', '数据3-2', '数据3-3'],
# # ]

# # # 计算当前已填充数据的行数，以便从下一行开始填充
# # start_row = 2

# # # 填充数据
# # for row_index, row_data in enumerate(data_to_fill, start=start_row):
# #     for col_index, value in enumerate(row_data, start=2):  # 从第1列开始填充
# #         sheet.cell(row=row_index, column=col_index, value=value)
# # # 保存为新的 Excel 文件
# # output_file = 'output.xlsx'
# # workbook.save(output_file)

# import re

# df = "CH1：电压：19.996 电流：0.002"
# pattern = r"CH1：电压：([-+]?\d*\.\d+) 电流：([-+]?\d*\.\d+)"
# match = re.search(pattern, df)
# if match:
#     print("匹配到数据：", match.group(1), match.group(2))
# else:
#     print("没有匹配到数据")


# list = Tool.init_execl_list()
# print(list)


# # 创建几个计数器实例
# counter1 = Counter()
# counter2 = Counter()

# # 修改计数器的计数
# counter1.increment()
# counter1.increment()
# counter2.increment()

# # 打印每个实例的计数和总体计数
# print("各个实例的计数:", Counter.get_instance_counts())
# print("总计数:", Counter.get_total_count())

# # 让counter1减少计数
# counter1.decrement()

# # 再次打印计数
# print("各个实例的计数:", Counter.get_instance_counts())
# print("总计数:", Counter.get_total_count())

# get_point()

# import sys
# from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow

# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("鼠标点击示例")
#         self.setGeometry(100, 100, 400, 300)
        
#         self.label = QLabel("请点击鼠标左键或右键", self)
#         self.label.setGeometry(50, 100, 300, 50)

#     def mousePressEvent(self, event):
#         if event.button() == 1:  # 左键
#             self.label.setText("左键点击")
#         elif event.button() == 2:  # 右键
#             self.label.setText("右键点击")

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = MainWindow()
#     window.show()
#     sys.exit(app.exec_())



# def handle_client_connection(self,client_socket):
#         try:
#             data = client_socket.recv(1024)
#             if data:
#                 hex_data = [f'{byte:02X}' for byte in data]
#                 # print("Received data in hex format:", hex_data)
#                 # 将收到的数据发送回client
#                 self.send_data(client_socket, data)
                
#                 # 解析数据
#                 type = hex_data[4]+hex_data[5]
#                 No = hex_data[6]
#                 command = hex_data[7]+hex_data[8]
#                 if command == "FE01":
#                     col = hex_data[9]
#                     # 输出控制
#                     if type == "0101":
#                         # 方形电源控制
#                         if col == "01":
#                             self.Power_dict_square[int(No, 16)-1].output_open()
#                             print(f"方形电源{int(No, 16)}打开")
#                         elif col == "00":
#                             self.Power_dict_square[int(No, 16)-1].output_close()
#                             print(f"方形电源{int(No, 16)}关闭")
#                     elif type == "0102":
#                         # 长条电源控制
#                         if col == "01":
#                             self.Power_dict_long[int(No, 16)-1].output_open()
#                             print(f"长条电源{int(No, 16)}打开")
#                         elif col == "00":
#                             self.Power_dict_long[int(No, 16)-1].output_close()
#                             print(f"长条电源{int(No, 16)}关闭")

#                 if command == "FE02":
#                     # 全部电源控制
#                     if hex_data[9] == "01":
#                         self.ALL_power_open()
#                         print("全部电源打开")
#                     elif hex_data[9] == "00":
#                         self.ALL_power_close()
#                         print("全部电源关闭")

#                 if command == "FE04":
#                     # 设置电源电压
#                     if type == "0101":
#                         # 方形电源控制
#                         # CH1
#                         vol = hex_data[9]+hex_data[10]+hex_data[11]+hex_data[12]
#                         vol_f = struct.unpack('!f', bytes.fromhex(vol))[0]
#                         self.Power_dict_square[int(No, 16)-1].V_set(1,vol_f)
#                         print(f"方形电源{int(No, 16)}设置电压{vol_f}")
#                         # CH2
#                         vol = hex_data[13]+hex_data[14]+hex_data[15]+hex_data[16]
#                         vol_f = struct.unpack('!f', bytes.fromhex(vol))[0]
#                         self.Power_dict_square[int(No, 16)-1].V_set(2,vol_f)
#                         print(f"方形电源{int(No, 16)}设置电压{vol_f}")
#                     elif type == "0102":
#                         # 长条电源控制
#                         vol = hex_data[9]+hex_data[10]+hex_data[11]+hex_data[12]
#                         vol_f = struct.unpack('!f', bytes.fromhex(vol))[0]
#                         self.Power_dict_long[int(No, 16)-1].V_set(vol_f)
#                         print(f"长条电源{int(No, 16)}设置电压{vol_f}")

#                 if command == "FE05":
#                     # 设置电源电流
#                     if type == "0101":
#                         # 方形电源控制
#                         # CH1
#                         cur = hex_data[9]+hex_data[10]+hex_data[11]+hex_data[12]
#                         cur_f = struct.unpack('!f', bytes.fromhex(cur))[0]
#                         self.Power_dict_square[int(No, 16)-1].I_set(1,cur_f)
#                         print(f"方形电源{int(No, 16)}设置电流{cur_f}")
#                         # CH2
#                         cur = hex_data[13]+hex_data[14]+hex_data[15]+hex_data[16]
#                         cur_f = struct.unpack('!f', bytes.fromhex(cur))[0]
#                         self.Power_dict_square[int(No, 16)-1].I_set(2,cur_f)
#                         print(f"方形电源{int(No, 16)}设置电流{cur_f}")
#                     elif type == "0102":
#                         # 长条电源控制
#                         cur = hex_data[9]+hex_data[10]+hex_data[11]+hex_data[12]
#                         cur_f = struct.unpack('!f', bytes.fromhex(cur))[0]
#                         self.Power_dict_long[int(No, 16)-1].I_set(cur_f)
#                         print(f"长条电源{int(No, 16)}设置电流{cur_f}")

#                 if command == "FE06":
#                     # 保存数据
#                     if type == "0101":
#                         # 方形电源控制
#                         power = self.Power_dict_square[int(No, 16)-1]
#                         if power.checkplot() == False:
#                             power.start_plot()
#                             time.sleep(1)
#                         self.excel.write_execl(power.save_data())
#                         print(f"方形电源{int(No, 16)}保存数据")
#                     elif type == "0102":
#                         # 长条电源控制
#                         power = self.Power_dict_long[0]
#                         if power.checkplot() == False:
#                             power.start_plot()
#                             time.sleep(2)
#                         self.excel.write_execl(power.save_data())
#                         print(f"长条电源{int(No, 16)}保存数据")

#                 if command == "FE07":
#                     # 全电源保存
#                     # 创建一个EXCEL文件，保存采集的数据
#                     if not os.path.exists(f"./电源采集数据/"):
#                         os.mkdir(f"./电源采集数据/")
#                     name = ""
#                     if hex_data[9] == "01":
#                         self.start_all_plot()
#                         time.sleep(2)
#                         print(f"性能测试前电流保存数据")
#                         name = "性能测试前电流"
#                         excel = execl_file()
#                         excel.read_execl(name)
#                         for i in range(len(self.Power_dict_square)):
#                             excel.write_execl(self.Power_dict_square[i].save_data())
#                         excel.write_execl(self.Power_dict_long[0].save_data())
#                         excel.save_execl(name)
#                     else:
#                         print(f"性能测试后电流保存数据")
#                         name = "性能测试后电流"
#                         excel = execl_file()
#                         excel.read_execl(name)
#                         for i in range(len(self.Power_dict_square)):
#                             excel.write_execl(self.Power_dict_square[i].save_data())
#                         excel.write_execl(self.Power_dict_long[0].save_data())
#                         excel.save_execl(name)

#                 if command == "FEA1":
#                     # 开始记录
#                     self.start_all_plot();
#                     excel_No = hex_data[9]
#                     self.excel.read_execl(excel_name[excel_No])
#                     print(f"开始记录{excel_name[excel_No]}")

#                 if command == "FEA2":
#                     # 停止记录
#                     excel_No = hex_data[9]
#                     self.excel.save_execl(excel_name[excel_No])
#                     print(f"停止记录")

#                 hex_data.clear()
#         except Exception as e:
#             print(f"处理客户端连接时出错::{e}")
#         finally:
#             client_socket.close()

# import sys
# from Projects.蓝转台.方形电源控制 import *
# from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QStackedWidget, QLabel


# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
        
#         self.setWindowTitle("多页面应用程序")
        
#         self.central_widget = QWidget()
#         self.setCentralWidget(self.central_widget)
        

#         # 创建堆叠窗口以切换页面
#         self.stacked_widget = QStackedWidget()
        
#         # 创建自定义页面对象
#         self.page1 = SquarePower("1")
#         self.page2 = SquarePower("2")
#         self.page3 = SquarePower("3")

#         # 将页面添加到堆叠窗口
#         self.stacked_widget.addWidget(self.page1)
#         self.stacked_widget.addWidget(self.page2)
#         self.stacked_widget.addWidget(self.page3)

#         # 创建按钮
#         self.button1 = QPushButton("打开页面 1")
#         self.button2 = QPushButton("打开页面 2")
#         self.button3 = QPushButton("打开页面 3")

#         # 连接按钮点击事件
#         self.button1.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.page1))
#         self.button2.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.page2))
#         self.button3.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.page3))

#         # 布局管理
#         button_layout = QVBoxLayout()
#         button_layout.addWidget(self.button1)
#         button_layout.addWidget(self.button2)
#         button_layout.addWidget(self.button3)

#         main_layout = QVBoxLayout(self.central_widget)
#         main_layout.addLayout(button_layout)
#         main_layout.addWidget(self.stacked_widget)

# if __name__ == "__main__":
#     # QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
#     app = QApplication(sys.argv)
#     window = MainWindow()
#     window.resize(400, 300)
#     window.show()
#     sys.exit(app.exec_())

