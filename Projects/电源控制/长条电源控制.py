<<<<<<< HEAD
'''
@工程 ：UpperPc 
@文件 ：电源控制.py
@作者 ：FTFH3
@日期 ：2023/10/12 16:30
@功能 ：
@方法 ：
=======
"""
长条电源控制模块。
>>>>>>> 3e78017 (initial commit)

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
<<<<<<< HEAD
'''
=======
"""
>>>>>>> 3e78017 (initial commit)
from datetime import datetime
import threading,dill
import time,os,math
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from bitstring import *
# from Utility.Datebase.Database import DataBase
# from Utility.Function.FuncMng import FuncMng
from .长条电源_UI import Ui_Form

import pandas as pd
import multiprocessing as mp
from .psw_xx_xx import psw_xx_xx

from .MyPlot import MyPlot
from .tool import Tool

<<<<<<< HEAD
TOTAL_SEC=20 #图上显示的时间时间长度
TIME_GAP=25 #采样间隔TIME_GAP个点取一个数字
POINT_NUM=int(100/25*TOTAL_SEC) #图上显示的点数
MAX_DEFLECTION_FAILURES=3 #拉偏操作最大连续失败次数
MAX_PLOT_FAILURES=3 #采集数据最大连续失败次数

=======
TOTAL_SEC = 20
TIME_GAP = 25
POINT_NUM = int(100 / TIME_GAP * TOTAL_SEC)
MAX_DEFLECTION_FAILURES = 3
MAX_PLOT_FAILURES = 3
PLOT_VOLTAGE_KEY = "电压"
PLOT_CURRENT_KEY = "电流"
DATA_DIR = os.path.join(".", "电源采集数据")
>>>>>>> 3e78017 (initial commit)
class LongPower(QtWidgets.QWidget,Ui_Form):
    instances = []
    VsetCol = []
    IsetCol = []
    VoutCol = []
    IoutCol = []
    name = '11'
    sigInfo = pyqtSignal(str)
    start_signal = pyqtSignal([str, float, float])
    current_warn = pyqtSignal([str, str, str])
    volatge_signal = pyqtSignal(dict)
    current_signal = pyqtSignal(dict)
    dataUpSignal = pyqtSignal(str)
    tcp_deflect =pyqtSignal([str, bool])
    _tcp_invoke_signal = pyqtSignal()

    def __init__(self, name):
        super(LongPower,self).__init__()
        self.name = name
<<<<<<< HEAD
        self.instances.append(self)
        self.setupUi(self)

=======
        self.setupUi(self)

        # 先完成拉偏相关成员初始化，避免对象在初始化未完成时被外部调用。
        self.deflectionTimer = QtCore.QTimer(self)
        self.deflectionTimer.timeout.connect(self._deflection_step)
        self.deflection_mode = None  # "Higher", "Lower", "Normal"
        self.deflection_notice = True
        self._deflection_fail_count = 0

>>>>>>> 3e78017 (initial commit)
        self.isConnected = False
        self.isOutput = False
        self.isListen = False
        self.findFlag = False
        self.found = False

        self.CurrentV = 0
        self.CurrentI = 0

        self.StopFlag = True
        self.pressNo = False
        self.lagtime = 1
        self.safty = 100
        self.psw = psw_xx_xx()

        self.btn_Control(False, False, False, False, False, False, False)

        self.portcheck.clicked.connect(lambda: Tool.port_check(self.portchoose))
        self.portopen.clicked.connect(self.power_port_open)
        self.portclose.clicked.connect(self.power_port_close)
        self.CH1_V_send.clicked.connect(lambda: self.V_set())
        self.CH1_I_send.clicked.connect(lambda: self.I_set())
        self.CH1_V_check.clicked.connect(self.V_get)
        self.CH1_I_check.clicked.connect(self.I_get)

        self.sendALL.clicked.connect(self.sendALLData)
        self.checkALL.clicked.connect(self.checkALLData)

        self.start_btn.clicked.connect(self.output_open)
        self.stop_btn.clicked.connect(self.output_close)

        self.start_listen.clicked.connect(self.start_plot)
        self.stop_listen.clicked.connect(self.close_plot)

        self.volatge_signal.connect(lambda x: self.volatge_layout.updateData(x))
        self.current_signal.connect(lambda x: self.current_layout.updateData(x))

        self.CH1_V.setText("42")
        self.CH1_I.setText("3.5")

        self.sigInfo.connect(self.show_msg)

<<<<<<< HEAD
        #初始化右侧绘图
        da = {"电压": []}
        self.volatge_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道1
        self.channel1.addWidget( self.volatge_layout)


        da = {"电流": []}
        self.current_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道2
=======
        # 初始化右侧图表
        da = {PLOT_VOLTAGE_KEY: []}
        self.volatge_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)
        self.channel1.addWidget( self.volatge_layout)


        da = {PLOT_CURRENT_KEY: []}
        self.current_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)
>>>>>>> 3e78017 (initial commit)
        self.channel2.addWidget( self.current_layout)

        self.plot_thread = threading.Thread(target=self.plot_callback)

        Tool.port_check(self.portchoose)

<<<<<<< HEAD
        # 统一的拉偏测试Timer和模式控制
        self.deflectionTimer = QtCore.QTimer()
        self.deflectionTimer.timeout.connect(self._deflection_step)
        self.deflection_mode = None  # "Higher", "Lower", "Normal"
        self.deflection_notice = True  # 是否弹窗提示
        self._deflection_fail_count = 0

        # 按钮连接到统一的拉偏测试接口
=======
        # 按钮连接到统一的拉偏测试入口
>>>>>>> 3e78017 (initial commit)
        self.Btn_to36.clicked.connect(lambda: self.start_deflection("Lower", notice=True))
        self.Btn_to45.clicked.connect(lambda: self.start_deflection("Higher", notice=True))
        self.Btn_back42.clicked.connect(lambda: self.start_deflection("Normal", notice=True))
        
        self.tcp_deflect.connect(self.start_deflection)

<<<<<<< HEAD
        # TCP线程安全调用机制：确保串口操作在Qt主线程中执行
=======
        # TCP 线程安全调用机制：确保串口操作在 Qt 主线程中执行
>>>>>>> 3e78017 (initial commit)
        self._tcp_invoke_lock = threading.Lock()
        self._tcp_op_event = threading.Event()
        self._tcp_op_func = None
        self._tcp_op_result = None
        self._tcp_invoke_signal.connect(self._on_tcp_invoke)
<<<<<<< HEAD

    def _on_tcp_invoke(self):
        """槽函数：在Qt主线程中执行TCP请求的操作"""
=======
        self.instances.append(self)

    def _ensure_deflection_timer(self):
        if not hasattr(self, "deflectionTimer"):
            self.deflectionTimer = QtCore.QTimer(self)
            self.deflectionTimer.timeout.connect(self._deflection_step)
        if not hasattr(self, "deflection_mode"):
            self.deflection_mode = None
        if not hasattr(self, "deflection_notice"):
            self.deflection_notice = True
        if not hasattr(self, "_deflection_fail_count"):
            self._deflection_fail_count = 0

    def _on_tcp_invoke(self):
        """在 Qt 主线程中执行 TCP 请求对应的操作。"""
>>>>>>> 3e78017 (initial commit)
        if self._tcp_op_func:
            try:
                self._tcp_op_result = self._tcp_op_func()
            except Exception as e:
                self._tcp_op_result = [False, str(e)]
            self._tcp_op_event.set()

    def _invoke_in_main_thread(self, func, timeout=30):
<<<<<<< HEAD
        """从TCP子线程安全调用需要在主线程执行的函数，阻塞等待结果"""
=======
        """从 TCP 子线程安全调用需要在主线程执行的函数，并等待结果。"""
>>>>>>> 3e78017 (initial commit)
        with self._tcp_invoke_lock:
            self._tcp_op_event.clear()
            self._tcp_op_func = func
            self._tcp_invoke_signal.emit()
            if self._tcp_op_event.wait(timeout=timeout):
                return self._tcp_op_result
            return [False, "Operation timed out"]

<<<<<<< HEAD
=======

>>>>>>> 3e78017 (initial commit)
    def invoke_tcp_power_on(self):
        return self._invoke_in_main_thread(self.output_open_tcp)

    def invoke_tcp_power_off(self):
        return self._invoke_in_main_thread(self.output_close_tcp)

    def invoke_tcp_connect(self):
        return self._invoke_in_main_thread(self.port_open)

<<<<<<< HEAD
=======
    def invoke_tcp_set_voltage(self, channel, voltage):
        return self._invoke_in_main_thread(lambda: self._tcp_set_voltage(channel, voltage))

    def invoke_tcp_set_current(self, channel, current):
        return self._invoke_in_main_thread(lambda: self._tcp_set_current(channel, current))

    def _tcp_set_voltage(self, channel, voltage):
        if channel != 1:
            return [False, "PSW only supports channel 1"]
        if not self.isConnected:
            return [False, "Port not connected"]
        self.V_set(voltage)
        return [True, ""]

    def _tcp_set_current(self, channel, current):
        if channel != 1:
            return [False, "PSW only supports channel 1"]
        if not self.isConnected:
            return [False, "Port not connected"]
        self.I_set(current)
        return [True, ""]

>>>>>>> 3e78017 (initial commit)
    def btn_Control(self, start_btn=None, stop_btn=None, start_listen=None, stop_listen=None, Btn_to36=None, Btn_to45=None, Btn_back42=None):
        if start_btn is not None:
            self.start_btn.setEnabled(start_btn)
        if stop_btn is not None:
            self.stop_btn.setEnabled(stop_btn)
        if start_listen is not None:
            self.start_listen.setEnabled(start_listen)
        if stop_listen is not None:
            self.stop_listen.setEnabled(stop_listen)
        if Btn_to36 is not None:
            self.Btn_to36.setEnabled(Btn_to36)
        if Btn_to45 is not None:
            self.Btn_to45.setEnabled(Btn_to45)
        if Btn_back42 is not None:
            self.Btn_back42.setEnabled(Btn_back42)

    def start_deflection(self, direction: str, notice: bool = True):
        """
<<<<<<< HEAD
        统一的拉偏测试启动函数
        :param direction: 拉偏方向 - "Higher"(向上到45V), "Lower"(向下到36V), "Normal"(回到42V)
        :param notice: 是否在完成时弹窗提示
        :return: [成功标志, 消息]
        """
=======
        统一的拉偏测试启动函数。

        :param direction: 拉偏方向，"Higher"(向上到 45V)、"Lower"(向下到 36V)、"Normal"(回到 42V)
        :param notice: 是否在完成时弹窗提示
        :return: [成功标志, 消息]
        """
        self._ensure_deflection_timer()

>>>>>>> 3e78017 (initial commit)
        if not self.isConnected:
            return [False, "Port not connected"]
        
        if direction not in ["Higher", "Lower", "Normal"]:
            return [False, f"Invalid direction: {direction}"]
        
        # 重置失败计数，设置模式和通知标志
        self._deflection_fail_count = 0
        self.deflection_mode = direction
        self.deflection_notice = notice
        
<<<<<<< HEAD
        # 禁用其他按钮，根据当前模式启用相应按钮
=======
        # 根据当前拉偏模式更新按钮状态和提示信息
>>>>>>> 3e78017 (initial commit)
        if direction == "Higher":
            self.btn_Control(Btn_to36=False, Btn_to45=True, Btn_back42=False)
            self.sigInfo.emit("开始向上拉偏到45V")
        elif direction == "Lower":
            self.btn_Control(Btn_to36=True, Btn_to45=False, Btn_back42=False)
            self.sigInfo.emit("开始向下拉偏到36V")
        elif direction == "Normal":
            self.btn_Control(Btn_to36=False, Btn_to45=False, Btn_back42=True)
            self.sigInfo.emit("开始回到默认42V")
<<<<<<< HEAD
        
        # 启动Timer
        self.deflectionTimer.start(1000)
        return [True, ""]
    
    def stop_deflection(self):
        """停止拉偏测试"""
=======

        self.deflectionTimer.start(1000)
        return [True, ""]

    def stop_deflection(self):
        """停止拉偏测试。"""
        self._ensure_deflection_timer()
>>>>>>> 3e78017 (initial commit)
        self.deflectionTimer.stop()
        self.deflection_mode = None
        self._deflection_fail_count = 0
        self.btn_Control(Btn_to36=True, Btn_to45=True, Btn_back42=True)
<<<<<<< HEAD
    
    def _deflection_step(self):
        """拉偏测试的单步执行（Timer回调函数）"""
=======

    def _deflection_step(self):
        """Timer 回调：执行一次拉偏步进。"""
>>>>>>> 3e78017 (initial commit)
        try:
            if self.deflection_mode == "Lower":
                self._deflect_to_36()
            elif self.deflection_mode == "Higher":
                self._deflect_to_45()
            elif self.deflection_mode == "Normal":
                self._deflect_to_42()
            self._deflection_fail_count = 0
        except Exception as e:
            self._deflection_fail_count += 1
            self.sigInfo.emit(f"拉偏操作异常({self._deflection_fail_count}/{MAX_DEFLECTION_FAILURES}): {e}")
            if self._deflection_fail_count >= MAX_DEFLECTION_FAILURES:
                self.sigInfo.emit("串口连续异常，已自动停止拉偏")
                self.stop_deflection()
<<<<<<< HEAD
    
    def _deflect_to_36(self):
        """向下拉偏到36V"""
=======

    def _deflect_to_36(self):
        """向下拉偏到 36V。"""
>>>>>>> 3e78017 (initial commit)
        if math.isclose(self.CurrentV, 36, abs_tol=0.1) or self.CurrentV < 35.9:
            self.sigInfo.emit("已达到36V")
            self.deflectionTimer.stop()
            self.btn_Control(Btn_to45=True, Btn_back42=True)
            if self.deflection_notice:
                QMessageBox.information(self, "提示", "已达到36V")
            return
        self.V_set(round(self.CurrentV, 1) - 0.1)
<<<<<<< HEAD
    
    def _deflect_to_45(self):
        """向上拉偏到45V"""
=======

    def _deflect_to_45(self):
        """向上拉偏到 45V。"""
>>>>>>> 3e78017 (initial commit)
        if math.isclose(self.CurrentV, 45, abs_tol=0.1) or self.CurrentV > 45.1:
            self.sigInfo.emit("已达到45V")
            self.deflectionTimer.stop()
            self.btn_Control(Btn_to36=True, Btn_back42=True)
            if self.deflection_notice:
                QMessageBox.information(self, "提示", "已达到45V")
            return
        self.V_set(round(self.CurrentV, 1) + 0.1)
<<<<<<< HEAD
    
    def _deflect_to_42(self):
        """回到默认42V"""
=======

    def _deflect_to_42(self):
        """回到默认 42V。"""
>>>>>>> 3e78017 (initial commit)
        if math.isclose(self.CurrentV, 42, abs_tol=0.1) \
            or (self.CurrentV >= 41 and self.CurrentV <= 42 and (self.CurrentV + 0.1) > 42) \
            or (self.CurrentV <= 43 and self.CurrentV >= 42 and (self.CurrentV - 0.1) < 42):
            self.V_set(42)
            self.sigInfo.emit("已回到42V")
            self.deflectionTimer.stop()
            self.btn_Control(Btn_to36=True, Btn_to45=True)
            if self.deflection_notice:
                QMessageBox.information(self, "提示", "已回到42V")
            return
        self.V_set((round(self.CurrentV, 1) - 0.1) if self.CurrentV > 42 else (round(self.CurrentV, 1) + 0.1))


<<<<<<< HEAD
    def findThread(self, name):
        # print("开始监看")
=======


    def findThread(self, name):
>>>>>>> 3e78017 (initial commit)
        self.sigInfo.emit("开始监看")
        while self.findFlag:
            if Tool.check_window_contains_keyword(name):
                self.sigInfo.emit("找到终端")
<<<<<<< HEAD
                # print("找到终端")
=======
>>>>>>> 3e78017 (initial commit)
                self.found = True
                self.findFlag = False
                break
            time.sleep(1)


    def show_msg(self, info):
        # 显示提示
        self.msg.moveCursor(QTextCursor.End)
        self.msg.insertPlainText(f"{info}\n")


    def power_port_open(self):
        re = self.port_open()
        if re[0]:
            self.btn_Control(start_btn=True, stop_btn=True, start_listen=True, stop_listen=False, Btn_to36=False, Btn_to45=False, Btn_back42=False)
            QMessageBox.information(self, "提示", f"已连接{self.portchoose.currentText()}")

<<<<<<< HEAD
    def port_open(self):
        if self.isConnected:
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
=======
    def port_open(self, show_error=True):
        if self.isConnected:
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
            Tool.update_config_option("Serial", "power_supply_long", self.portchoose.currentText())
>>>>>>> 3e78017 (initial commit)
            return [True, ""]
        try:
            self.psw.open(self.portchoose.currentText())
            V = self.psw.getVoltage()
            self.powername.setText(f"{V}V")
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
            self.isConnected = True
<<<<<<< HEAD
            return [True, ""]
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")
            return [False, ""]
=======
            Tool.update_config_option("Serial", "power_supply_long", self.portchoose.currentText())
            return [True, ""]
        except Exception as e:
            try:
                if getattr(self.psw, "serial", None):
                    self.psw.close()
            except Exception:
                pass
            if show_error:
                QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")
            return [False, ""]

    def startup_port_open(self):
        re = self.port_open(show_error=False)
        if re[0]:
            self.btn_Control(start_btn=True, stop_btn=True, start_listen=True, stop_listen=False, Btn_to36=False, Btn_to45=False, Btn_back42=False)
        return re
>>>>>>> 3e78017 (initial commit)
    
    def power_port_close(self):
        # 断开电源
        self.psw.close()
        self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
        self.isConnected = False
        self.btn_Control(False, False, False, False, False, False, False)
    
    def V_set(self, voltage=None):
        # 设置电压
        if voltage is None:
            voltage = float(self.CH1_V.text())
        self.psw.setVoltage(voltage)
        self.sigInfo.emit(f"已设置CH1电压为{voltage}")

    
    def I_set(self, current=None):
        # 设置电流
        if current is None:
            current = float(self.CH1_I.text())
        self.psw.setCurrent(current)
        self.sigInfo.emit(f"已设置CH1电流为{current}")


    def sendALLData(self):
        # 发送全部数据
        self.psw.setVoltage(float(self.CH1_V.text()))
        self.psw.setCurrent(float(self.CH1_I.text()))
<<<<<<< HEAD
        self.sigInfo.emit(f"已发送全部数据")

    def V_get(self):
        # 获取设置电压
        V = self.psw.getVoltage()
        # self.VoutCol[ch].clear()
        self.CH1_V_print.setText("电压："+str(V))
=======
        self.sigInfo.emit("已发送全部数据")

    def V_get(self):
        # 获取设定电压
        V = self.psw.getVoltage()
        # self.VoutCol[ch].clear()
        self.CH1_V_print.setText("电压：" + str(V))
>>>>>>> 3e78017 (initial commit)
        return V
    

    def I_get(self):
<<<<<<< HEAD
        # 获取设置电流
        I = self.psw.getCurrent()
        # self.IoutCol[ch].clear()
        self.CH1_I_print.setText("电流："+str(I))
=======
        # 获取设定电流
        I = self.psw.getCurrent()
        # self.IoutCol[ch].clear()
        self.CH1_I_print.setText("电流：" + str(I))
>>>>>>> 3e78017 (initial commit)
        return I
    

    def checkALLData(self):
        # 检查全部数据
        V,I = self.psw.getVoltage(), self.psw.getCurrent()
        self.CH1_V_print.setText("电压：%.3f" % V)
        self.CH1_I_print.setText("电流：%.3f" % I)
<<<<<<< HEAD
        self.sigInfo.emit(f"已检查全部数据")
=======
        self.sigInfo.emit("已检查全部数据")
>>>>>>> 3e78017 (initial commit)
        return [["%.3f"%V, "%.3f"%I]]

    
    def output_open(self):
        # 打开输出
        if self.isConnected:
            self.found = False
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.findFlag = True
            # thread = threading.Thread(target=self.findThread, args=("综合测试终端",))
            # thread.start()
            self.sendALLData()
            self.start_signal.emit(self.name, self.V_get(), self.I_get())
            if self.pressNo:
                self.pressNo = False
                return
            self.start_plot()
            time.sleep(1)
            self.psw.enableOutput()
<<<<<<< HEAD
            self.sigInfo.emit(f"已打开电源输出")
            self.isOutput = True
            self.btn_Control(start_btn=False, stop_btn=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)
        else:
            self.sigInfo.emit(f"请先连接电源")
=======
            self.sigInfo.emit("已打开电源输出")
            self.isOutput = True
            self.btn_Control(start_btn=False, stop_btn=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)
        else:
            self.sigInfo.emit("请先连接电源")
>>>>>>> 3e78017 (initial commit)
            return
    
    
    def output_open_tcp(self):
        # 打开输出
        if self.isConnected:    
            self.found = False
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.findFlag = True
            # thread = threading.Thread(target=self.findThread, args=("综合测试终端",))
            # thread.start()
            self.sendALLData()
            # self.start_signal.emit(self.name, self.V_get(), self.I_get())
            # if self.pressNo:
            #     self.pressNo = False
            #     return
            self.start_plot()
            time.sleep(1)
            self.psw.enableOutput()
<<<<<<< HEAD
            self.sigInfo.emit(f"已打开电源输出")
=======
            self.sigInfo.emit("已打开电源输出")
>>>>>>> 3e78017 (initial commit)
            self.isOutput = True
            self.btn_Control(start_btn=False, stop_btn=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)
            return [True, ""]
        else:
<<<<<<< HEAD
            self.sigInfo.emit(f"请先连接电源")
=======
            self.sigInfo.emit("请先连接电源")
>>>>>>> 3e78017 (initial commit)
            return [False, "Port not connected"]

    def output_close(self):
        # 关闭输出
        if self.found:
            self.found = False
<<<<<<< HEAD
            self.dataUpSignal.emit(f"./电源采集数据/{self.name}_{self.start_time}.csv")
        self.psw.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
=======
            self.dataUpSignal.emit(os.path.join(DATA_DIR, f"{self.name}_{self.start_time}.csv"))
        self.psw.enableOutput(False)
        self.sigInfo.emit("已关闭电源输出")
>>>>>>> 3e78017 (initial commit)
        self.isOutput = False
        time.sleep(1)
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.btn_Control(start_btn=True, stop_btn=True, start_listen=True, Btn_to36=False, Btn_to45=False, Btn_back42=False)

    
    def output_close_tcp(self):
        # 关闭输出
        # if self.found:
        #     self.found = False  
<<<<<<< HEAD
        #     self.dataUpSignal.emit(f"./电源采集数据/{self.name}_{self.start_time}.csv")
        self.psw.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
=======
        #     self.dataUpSignal.emit(os.path.join(DATA_DIR, f"{self.name}_{self.start_time}.csv"))
        self.psw.enableOutput(False)
        self.sigInfo.emit("已关闭电源输出")
>>>>>>> 3e78017 (initial commit)
        self.isOutput = False
        time.sleep(1)
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.btn_Control(start_btn=True, stop_btn=True, start_listen=True, Btn_to36=False, Btn_to45=False, Btn_back42=False)
        return [True, ""]


    def downDeflection_tcp(self, Con, notice: bool = False):
        """
<<<<<<< HEAD
        TCP远程控制拉偏测试接口
        :param Con: 拉偏方向 - "Higher"(向上到45V), "Lower"(向下到36V), "Normal"(回到42V)
=======
        TCP 远程控制拉偏测试接口。

        :param Con: 拉偏方向，"Higher"(向上到 45V)、"Lower"(向下到 36V)、"Normal"(回到 42V)
>>>>>>> 3e78017 (initial commit)
        :param notice: 是否在完成时弹窗提示，远程控制默认不弹窗
        :return: [成功标志, 消息]
        """
        return self.start_deflection(Con, notice=notice)


    def plot_callback(self):
<<<<<<< HEAD
        CH1_V = {"电压": 0}
        CH1_I = {"电流": 0}
=======
        CH1_V = {PLOT_VOLTAGE_KEY: 0}
        CH1_I = {PLOT_CURRENT_KEY: 0}
>>>>>>> 3e78017 (initial commit)
        fail_count = 0
        while not self.StopFlag:
            try:
                V, I = self.psw.getOutput()
                fail_count = 0
<<<<<<< HEAD
                CH1_V["电压"] = V
                CH1_I["电流"] = I
=======
                CH1_V[PLOT_VOLTAGE_KEY] = V
                CH1_I[PLOT_CURRENT_KEY] = I
>>>>>>> 3e78017 (initial commit)
                self.CurrentV = V
                self.CurrentI = I
                if I > self.safty:
                    self.StopFlag = True
                    self.current_warn.emit(f"{self.name}", f"CH1", f"{I}")
                self.volatge_signal.emit(CH1_V)
                self.current_signal.emit(CH1_I)
<<<<<<< HEAD
                if not os.path.exists(f"./电源采集数据/"):
                    os.mkdir(f"./电源采集数据/")
                if not os.path.exists(f"./电源采集数据/{self.name}_{self.start_time}.csv"):
                    with open(f"./电源采集数据/{self.name}_{self.start_time}.csv", "w", encoding='gbk') as f:
                        f.write("时间,CH1电压,CH1电流\n")
                with open(f"./电源采集数据/{self.name}_{self.start_time}.csv", "a", encoding='gbk') as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},{CH1_V['电压']},{CH1_I['电流']}\n")
=======
                os.makedirs(DATA_DIR, exist_ok=True)
                csv_path = os.path.join(DATA_DIR, f"{self.name}_{self.start_time}.csv")
                if not os.path.exists(csv_path):
                    with open(csv_path, "w", encoding="gbk") as f:
                        f.write("时间,CH1电压,CH1电流\n")
                with open(csv_path, "a", encoding="gbk") as f:
                    f.write(
                        f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},"
                        f"{CH1_V[PLOT_VOLTAGE_KEY]},{CH1_I[PLOT_CURRENT_KEY]}\n"
                    )
>>>>>>> 3e78017 (initial commit)
                time.sleep(0.1)
            except Exception as e:
                fail_count += 1
                self.sigInfo.emit(f"采集数据异常({fail_count}/{MAX_PLOT_FAILURES}): {e}")
                if fail_count >= MAX_PLOT_FAILURES:
                    self.sigInfo.emit("串口连续异常，已自动停止采集")
                    self.StopFlag = True
                    break
                time.sleep(1)

    def get_value(self):
        return [self.CurrentV, self.CurrentI]

    def start_plot(self):
        # 启动动态画图
        self.StopFlag = False
        if not self.plot_thread.is_alive():
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
<<<<<<< HEAD
            self.sigInfo.emit(f"已开启采集")
        else:
            self.sigInfo.emit(f"采集已开启")
=======
            self.sigInfo.emit("已开启采集")
        else:
            self.sigInfo.emit("采集已开启")
>>>>>>> 3e78017 (initial commit)
        self.btn_Control(start_listen=False, stop_listen=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)

    def close_plot(self):
        # 关闭动态画图
        self.StopFlag = True
        if self.plot_thread.is_alive():
            self.plot_thread.join()
<<<<<<< HEAD
            self.sigInfo.emit(f"已关闭采集")
        else:
            self.sigInfo.emit(f"采集已关闭")
=======
            self.sigInfo.emit("已关闭采集")
        else:
            self.sigInfo.emit("采集已关闭")
>>>>>>> 3e78017 (initial commit)
        self.btn_Control(start_listen=True, stop_listen=False, Btn_to36=False, Btn_to45=False, Btn_back42=False)


    def checkplot(self):
        return self.plot_thread.is_alive()
        

    @classmethod
    def get_instances(cls):
        return cls.instances
    
    def __del__(self):
<<<<<<< HEAD
        self.instances.remove(self)
=======
        if self in self.instances:
            self.instances.remove(self)
>>>>>>> 3e78017 (initial commit)
