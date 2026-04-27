from datetime import datetime
import os
import threading
import time

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QTextCursor

from .MyPlot import MyPlot
from .gpp_xx_xx import GPPPowerSupply
from .tool import Tool


TOTAL_SEC = 20
TIME_GAP = 25
POINT_NUM = int(100 / TIME_GAP * TOTAL_SEC)
MAX_PLOT_FAILURES = 3
PLOT_VOLTAGE_KEY = "电压"
PLOT_CURRENT_KEY = "电流"
DATA_DIR = os.path.join(".", "电源采集数据")


class GPPPower(QtWidgets.QWidget):
    instances = []
    sigInfo = pyqtSignal(str)
    current_warn = pyqtSignal([str, str, str])
    channel1_signal = pyqtSignal(dict)
    channel2_signal = pyqtSignal(dict)
    channel3_signal = pyqtSignal(dict)
    _tcp_invoke_signal = pyqtSignal()

    def __init__(self, name):
        super(GPPPower, self).__init__()
        self.name = name
        self.isConnected = False
        self.isOutput = False
        self.StopFlag = True
        self.ch1_safty = 100
        self.ch2_safty = 100
        self.ch3_safty = 5
        self.gpp = GPPPowerSupply()
        self.CurrentValues = {
            1: [0.0, 0.0],
            2: [0.0, 0.0],
            3: [0.0, 0.0],
        }

        self._tcp_invoke_lock = threading.Lock()
        self._tcp_op_event = threading.Event()
        self._tcp_op_func = None
        self._tcp_op_result = None

        self._build_ui()
        self._bind_signals()
        self._init_plots()

        self.plot_thread = threading.Thread(target=self.plot_callback)
        self.instances.append(self)
        self.refresh_connection_options(show_message=False)

    def _build_ui(self):
        self.setObjectName(self.name)
        self.resize(1280, 820)
        self.setMinimumSize(1180, 760)

        root = QtWidgets.QGridLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.tabWidget = QtWidgets.QTabWidget(self)
        self.tabWidget.setMaximumWidth(680)
        power_tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(power_tab)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.setSpacing(8)

        title_row = QtWidgets.QHBoxLayout()
        self.portname = QtWidgets.QLabel("设备选择", power_tab)
        self.powername = QtWidgets.QLabel("", power_tab)
        title_row.addWidget(self.portname)
        title_row.addWidget(self.powername, 1)
        tab_layout.addLayout(title_row)

        port_row = QtWidgets.QHBoxLayout()
        self.portchoose = QtWidgets.QComboBox(power_tab)
        self.portcheck = QtWidgets.QPushButton("刷新设备", power_tab)
        port_row.addWidget(self.portchoose, 1)
        port_row.addWidget(self.portcheck)
        tab_layout.addLayout(port_row)

        self.transport_hint = QtWidgets.QLabel("", power_tab)
        self.transport_hint.setWordWrap(True)
        tab_layout.addWidget(self.transport_hint)

        port_btn_row = QtWidgets.QHBoxLayout()
        self.portopen = QtWidgets.QPushButton("打开连接", power_tab)
        self.portclose = QtWidgets.QPushButton("关闭连接", power_tab)
        port_btn_row.addWidget(self.portopen)
        port_btn_row.addWidget(self.portclose)
        tab_layout.addLayout(port_btn_row)

        tab_layout.addWidget(self._create_line())
        tab_layout.addWidget(self._build_set_group(power_tab))
        tab_layout.addWidget(self._create_line())
        tab_layout.addWidget(self._build_check_group(power_tab))
        tab_layout.addWidget(self._create_line())

        self.msg = QtWidgets.QTextEdit(power_tab)
        self.msg.setReadOnly(True)
        self.msg.setMinimumHeight(180)
        tab_layout.addWidget(self.msg)

        tab_layout.addWidget(self._create_line())

        control_row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("开始输出", power_tab)
        self.stop_btn = QtWidgets.QPushButton("停止输出", power_tab)
        control_row.addWidget(self.start_btn)
        control_row.addWidget(self.stop_btn)
        tab_layout.addLayout(control_row)

        listen_row = QtWidgets.QHBoxLayout()
        self.start_listen = QtWidgets.QPushButton("开始采集", power_tab)
        self.stop_listen = QtWidgets.QPushButton("停止采集", power_tab)
        listen_row.addWidget(self.start_listen)
        listen_row.addWidget(self.stop_listen)
        tab_layout.addLayout(listen_row)
        tab_layout.addStretch(1)

        self.tabWidget.addTab(power_tab, "电源")

        plot_widget = QtWidgets.QWidget(self)
        plot_layout = QtWidgets.QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(8)

        self.CH1_name = QtWidgets.QLineEdit("CH1", plot_widget)
        self.CH1_name.setReadOnly(True)
        plot_layout.addWidget(self.CH1_name)
        self.channel1_container = QtWidgets.QVBoxLayout()
        plot_layout.addLayout(self.channel1_container)

        self.CH2_name = QtWidgets.QLineEdit("CH2", plot_widget)
        self.CH2_name.setReadOnly(True)
        plot_layout.addWidget(self.CH2_name)
        self.channel2_container = QtWidgets.QVBoxLayout()
        plot_layout.addLayout(self.channel2_container)

        self.CH3_name = QtWidgets.QLineEdit("CH3", plot_widget)
        self.CH3_name.setReadOnly(True)
        plot_layout.addWidget(self.CH3_name)
        self.channel3_container = QtWidgets.QVBoxLayout()
        plot_layout.addLayout(self.channel3_container)

        root.addWidget(self.tabWidget, 0, 0)
        root.addWidget(plot_widget, 0, 1)
        root.setColumnStretch(1, 1)

        self.CH1_V.setText("42")
        self.CH1_I.setText("3.5")
        self.CH2_V.setText("42")
        self.CH2_I.setText("3.5")
        self.CH3_V.setCurrentText("5.0")

        self.btn_Control(False, False, False, False)

    def _bind_signals(self):
        self.portcheck.clicked.connect(lambda: self.refresh_connection_options(show_message=True))
        self.portopen.clicked.connect(self.power_port_open)
        self.portclose.clicked.connect(self.power_port_close)

        self.CH1_V_send.clicked.connect(lambda: self.V_set(1))
        self.CH1_I_send.clicked.connect(lambda: self.I_set(1))
        self.CH2_V_send.clicked.connect(lambda: self.V_set(2))
        self.CH2_I_send.clicked.connect(lambda: self.I_set(2))
        self.CH3_V_send.clicked.connect(lambda: self.V_set(3))

        self.CH1_V_check.clicked.connect(lambda: self.V_get(1))
        self.CH1_I_check.clicked.connect(lambda: self.I_get(1))
        self.CH2_V_check.clicked.connect(lambda: self.V_get(2))
        self.CH2_I_check.clicked.connect(lambda: self.I_get(2))
        self.CH3_V_check.clicked.connect(lambda: self.V_get(3))

        self.sendALL.clicked.connect(self.sendALLData)
        self.checkALL.clicked.connect(self.checkALLData)
        self.start_btn.clicked.connect(self.output_open)
        self.stop_btn.clicked.connect(self.output_close)
        self.start_listen.clicked.connect(self.start_plot)
        self.stop_listen.clicked.connect(self.close_plot)

        self.sigInfo.connect(self.show_msg)
        self.channel1_signal.connect(lambda x: self.channel1_layout.updateData(x))
        self.channel2_signal.connect(lambda x: self.channel2_layout.updateData(x))
        self.channel3_signal.connect(lambda x: self.channel3_layout.updateData(x))
        self._tcp_invoke_signal.connect(self._on_tcp_invoke)

    def _init_plots(self):
        self.channel1_layout = MyPlot(
            dataDict={PLOT_VOLTAGE_KEY: [], PLOT_CURRENT_KEY: []},
            dataLen=POINT_NUM,
        )
        self.channel1_container.addWidget(self.channel1_layout)

        self.channel2_layout = MyPlot(
            dataDict={PLOT_VOLTAGE_KEY: [], PLOT_CURRENT_KEY: []},
            dataLen=POINT_NUM,
        )
        self.channel2_container.addWidget(self.channel2_layout)

        self.channel3_layout = MyPlot(
            dataDict={PLOT_VOLTAGE_KEY: [], PLOT_CURRENT_KEY: []},
            dataLen=POINT_NUM,
        )
        self.channel3_container.addWidget(self.channel3_layout)

    def _build_set_group(self, parent):
        group = QtWidgets.QGroupBox("参数设置", parent)
        layout = QtWidgets.QGridLayout(group)
        layout.setColumnStretch(1, 1)

        self.CH1_V = QtWidgets.QLineEdit(group)
        self.CH1_I = QtWidgets.QLineEdit(group)
        self.CH2_V = QtWidgets.QLineEdit(group)
        self.CH2_I = QtWidgets.QLineEdit(group)
        self.CH3_V = QtWidgets.QComboBox(group)
        self.CH3_V.addItems(["1.8", "2.5", "3.3", "5.0"])

        self.CH1_V_send = QtWidgets.QPushButton("发送", group)
        self.CH1_I_send = QtWidgets.QPushButton("发送", group)
        self.CH2_V_send = QtWidgets.QPushButton("发送", group)
        self.CH2_I_send = QtWidgets.QPushButton("发送", group)
        self.CH3_V_send = QtWidgets.QPushButton("发送", group)

        layout.addWidget(QtWidgets.QLabel("CH1 电压(V)", group), 0, 0)
        layout.addWidget(self.CH1_V, 0, 1)
        layout.addWidget(self.CH1_V_send, 0, 2)

        layout.addWidget(QtWidgets.QLabel("CH1 电流(A)", group), 1, 0)
        layout.addWidget(self.CH1_I, 1, 1)
        layout.addWidget(self.CH1_I_send, 1, 2)

        layout.addWidget(QtWidgets.QLabel("CH2 电压(V)", group), 2, 0)
        layout.addWidget(self.CH2_V, 2, 1)
        layout.addWidget(self.CH2_V_send, 2, 2)

        layout.addWidget(QtWidgets.QLabel("CH2 电流(A)", group), 3, 0)
        layout.addWidget(self.CH2_I, 3, 1)
        layout.addWidget(self.CH2_I_send, 3, 2)

        layout.addWidget(QtWidgets.QLabel("CH3 电压(V)", group), 4, 0)
        layout.addWidget(self.CH3_V, 4, 1)
        layout.addWidget(self.CH3_V_send, 4, 2)

        self.sendALL = QtWidgets.QPushButton("发送全部数据", group)
        layout.addWidget(self.sendALL, 5, 0, 1, 3)
        return group

    def _build_check_group(self, parent):
        group = QtWidgets.QGroupBox("输出检查", parent)
        layout = QtWidgets.QGridLayout(group)
        layout.setColumnStretch(1, 1)

        self.CH1_V_print = self._create_display_edit(group)
        self.CH1_I_print = self._create_display_edit(group)
        self.CH2_V_print = self._create_display_edit(group)
        self.CH2_I_print = self._create_display_edit(group)
        self.CH3_V_print = self._create_display_edit(group)
        self.CH3_I_print = self._create_display_edit(group)

        self.CH1_V_check = QtWidgets.QPushButton("读取", group)
        self.CH1_I_check = QtWidgets.QPushButton("读取", group)
        self.CH2_V_check = QtWidgets.QPushButton("读取", group)
        self.CH2_I_check = QtWidgets.QPushButton("读取", group)
        self.CH3_V_check = QtWidgets.QPushButton("读取", group)

        layout.addWidget(self.CH1_V_print, 0, 0, 1, 2)
        layout.addWidget(self.CH1_V_check, 0, 2)
        layout.addWidget(self.CH1_I_print, 1, 0, 1, 2)
        layout.addWidget(self.CH1_I_check, 1, 2)

        layout.addWidget(self.CH2_V_print, 2, 0, 1, 2)
        layout.addWidget(self.CH2_V_check, 2, 2)
        layout.addWidget(self.CH2_I_print, 3, 0, 1, 2)
        layout.addWidget(self.CH2_I_check, 3, 2)

        layout.addWidget(self.CH3_V_print, 4, 0, 1, 2)
        layout.addWidget(self.CH3_V_check, 4, 2)
        layout.addWidget(self.CH3_I_print, 5, 0, 1, 2)

        self.checkALL = QtWidgets.QPushButton("检查全部数据", group)
        layout.addWidget(self.checkALL, 6, 0, 1, 3)
        return group

    def _create_display_edit(self, parent):
        edit = QtWidgets.QLineEdit(parent)
        edit.setReadOnly(True)
        return edit

    def _create_line(self):
        line = QtWidgets.QFrame(self)
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line

    def refresh_connection_options(self, show_message=False):
        current_resource = self.portchoose.currentText().strip()
        resources = GPPPowerSupply.list_available_resources()
        self.portchoose.clear()
        for resource in resources:
            self.portchoose.addItem(resource)

        if current_resource and current_resource in resources:
            self.portchoose.setCurrentText(current_resource)
        elif resources:
            self.portchoose.setCurrentIndex(0)

        hint = GPPPowerSupply.get_environment_hint()
        self.transport_hint.setText(hint)
        if hint:
            self.sigInfo.emit(hint)

        if show_message:
            if resources:
                QtWidgets.QMessageBox.information(self, "提示", f"检测到 {len(resources)} 个可用设备")
            else:
                QtWidgets.QMessageBox.warning(self, "提示", hint or "未检测到可用设备")

        return resources

    def _on_tcp_invoke(self):
        if self._tcp_op_func:
            try:
                self._tcp_op_result = self._tcp_op_func()
            except Exception as e:
                self._tcp_op_result = [False, str(e)]
            self._tcp_op_event.set()

    def _invoke_in_main_thread(self, func, timeout=30):
        with self._tcp_invoke_lock:
            self._tcp_op_event.clear()
            self._tcp_op_func = func
            self._tcp_invoke_signal.emit()
            if self._tcp_op_event.wait(timeout=timeout):
                return self._tcp_op_result
            return [False, "Operation timed out"]

    def btn_Control(self, start_btn=None, stop_btn=None, start_listen=None, stop_listen=None):
        if start_btn is not None:
            self.start_btn.setEnabled(start_btn)
        if stop_btn is not None:
            self.stop_btn.setEnabled(stop_btn)
        if start_listen is not None:
            self.start_listen.setEnabled(start_listen)
        if stop_listen is not None:
            self.stop_listen.setEnabled(stop_listen)

    def show_msg(self, info):
        self.msg.moveCursor(QTextCursor.End)
        self.msg.insertPlainText(f"{info}\n")

    def refresh_channel_names(self):
        ch1_v = self.gpp.getVoltage(1)
        ch1_i = self.gpp.getCurrent(1)
        ch2_v = self.gpp.getVoltage(2)
        ch2_i = self.gpp.getCurrent(2)
        ch3_v = self.gpp.getVoltage(3)

        self.powername.setText(self.gpp.get_idn())
        self.CH1_name.setText(f"CH1：{ch1_v:.3f}V / {ch1_i:.3f}A")
        self.CH2_name.setText(f"CH2：{ch2_v:.3f}V / {ch2_i:.3f}A")
        self.CH3_name.setText(f"CH3：{ch3_v:.1f}V / 固定 5A")

    def power_port_open(self):
        result = self.port_open()
        if result[0]:
            QtWidgets.QMessageBox.information(self, "提示", f"已连接 {self.portchoose.currentText()}\n{result[1]}")
        else:
            QtWidgets.QMessageBox.warning(self, "错误", result[1] if len(result) > 1 else "连接失败")

    def port_open(self, show_error=True):
        resource_name = self.portchoose.currentText().strip()
        if not resource_name:
            hint = GPPPowerSupply.get_environment_hint() or "未检测到可用设备"
            if show_error:
                QtWidgets.QMessageBox.warning(self, "错误", hint)
            return [False, hint]

        if self.isConnected:
            self.sigInfo.emit(f"已连接{resource_name}")
            Tool.update_config_option("Serial", "power_supply_gpp", resource_name)
            return [True, self.powername.text()]

        try:
            self.gpp.open(resource_name)
            self.refresh_channel_names()
            self.isConnected = True
            self.sigInfo.emit(f"已连接{resource_name}")
            Tool.update_config_option("Serial", "power_supply_gpp", resource_name)
            self.btn_Control(True, True, True, False)
            return [True, self.powername.text()]
        except Exception as e:
            try:
                self.gpp.close()
            except Exception:
                pass
            if show_error:
                QtWidgets.QMessageBox.warning(self, "错误", f"连接 {resource_name} 失败：{e}")
            return [False, str(e)]

    def startup_port_open(self):
        return self.port_open(show_error=False)

    def power_port_close(self):
        if self.plot_thread.is_alive():
            self.close_plot()
        try:
            self.gpp.close()
        finally:
            self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
            self.isConnected = False
            self.isOutput = False
            self.btn_Control(False, False, False, False)

    def V_set(self, ch, voltage=None):
        if voltage is None:
            if ch == 3:
                voltage = float(self.CH3_V.currentText())
            elif ch == 1:
                voltage = float(self.CH1_V.text())
            else:
                voltage = float(self.CH2_V.text())

        self.gpp.setVoltage(ch, voltage)
        self.sigInfo.emit(f"已设置CH{ch}通道电压为{float(voltage):.3f}V")
        self.refresh_channel_names()
        return float(voltage)

    def I_set(self, ch, current=None):
        if ch == 3:
            raise RuntimeError("CH3 电流固定，不能设置")
        if current is None:
            current = float(self.CH1_I.text()) if ch == 1 else float(self.CH2_I.text())
        self.gpp.setCurrent(ch, current)
        self.sigInfo.emit(f"已设置CH{ch}通道电流为{float(current):.3f}A")
        self.refresh_channel_names()
        return float(current)

    def sendALLData(self):
        self.V_set(1)
        self.I_set(1)
        self.V_set(2)
        self.I_set(2)
        self.V_set(3)
        self.sigInfo.emit("已发送全部数据")

    def V_get(self, ch):
        value = self.gpp.getVoltageOutput(ch)
        target = {
            1: self.CH1_V_print,
            2: self.CH2_V_print,
            3: self.CH3_V_print,
        }[ch]
        target.setText(f"电压：{value:.3f}")
        return value

    def I_get(self, ch):
        value = self.gpp.getCurrentOutput(ch)
        target = {
            1: self.CH1_I_print,
            2: self.CH2_I_print,
            3: self.CH3_I_print,
        }[ch]
        target.setText(f"电流：{value:.3f}")
        return value

    def checkALLData(self):
        data = [[]]
        for ch in (1, 2, 3):
            voltage = self.V_get(ch)
            current = self.I_get(ch)
            data[0].append(f"{voltage:.3f}")
            data[0].append(f"{current:.3f}")
        return data

    def output_open(self):
        if not self.isConnected:
            self.sigInfo.emit("请先连接电源")
            return

        self.sendALLData()
        self.start_plot()
        time.sleep(0.3)
        self.gpp.enableOutput(True)
        self.sigInfo.emit("已打开电源输出")
        self.isOutput = True
        self.btn_Control(False, True, True, True)

    def output_close(self):
        try:
            self.gpp.enableOutput(False)
        finally:
            self.sigInfo.emit("已关闭电源输出")
            self.isOutput = False
            if self.plot_thread.is_alive():
                self.StopFlag = True
                self.plot_thread.join()
            self.btn_Control(True, True, True, False)

    def plot_callback(self):
        channels = {
            1: {PLOT_VOLTAGE_KEY: 0.0, PLOT_CURRENT_KEY: 0.0},
            2: {PLOT_VOLTAGE_KEY: 0.0, PLOT_CURRENT_KEY: 0.0},
            3: {PLOT_VOLTAGE_KEY: 0.0, PLOT_CURRENT_KEY: 0.0},
        }
        fail_count = 0

        while not self.StopFlag:
            try:
                values = self.gpp.getOutput()
                fail_count = 0

                for index, channel in enumerate((1, 2, 3)):
                    voltage, current = values[index]
                    channels[channel][PLOT_VOLTAGE_KEY] = voltage
                    channels[channel][PLOT_CURRENT_KEY] = current
                    self.CurrentValues[channel] = [voltage, current]

                if channels[1][PLOT_CURRENT_KEY] >= self.ch1_safty:
                    self.gpp.enableOutput(False)
                    self.StopFlag = True
                    self.current_warn.emit(self.name, "CH1", f"{channels[1][PLOT_CURRENT_KEY]:.3f}")

                if channels[2][PLOT_CURRENT_KEY] >= self.ch2_safty:
                    self.gpp.enableOutput(False)
                    self.StopFlag = True
                    self.current_warn.emit(self.name, "CH2", f"{channels[2][PLOT_CURRENT_KEY]:.3f}")

                self.channel1_signal.emit(dict(channels[1]))
                self.channel2_signal.emit(dict(channels[2]))
                self.channel3_signal.emit(dict(channels[3]))
                self._append_csv(channels)
                time.sleep(0.1)
            except Exception as e:
                fail_count += 1
                self.sigInfo.emit(f"采集数据异常({fail_count}/{MAX_PLOT_FAILURES}): {e}")
                if fail_count >= MAX_PLOT_FAILURES:
                    self.sigInfo.emit("通信连续异常，已自动停止采集")
                    self.StopFlag = True
                    break
                time.sleep(1)

    def _append_csv(self, channels):
        if not os.path.exists(DATA_DIR):
            os.mkdir(DATA_DIR)

        file_path = os.path.join(DATA_DIR, f"{self.name}_{self.start_time}.csv")
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="gbk") as f:
                f.write("时间,CH1电压,CH1电流,CH2电压,CH2电流,CH3电压,CH3电流\n")

        with open(file_path, "a", encoding="gbk") as f:
            f.write(
                f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},"
                f"{channels[1][PLOT_VOLTAGE_KEY]},{channels[1][PLOT_CURRENT_KEY]},"
                f"{channels[2][PLOT_VOLTAGE_KEY]},{channels[2][PLOT_CURRENT_KEY]},"
                f"{channels[3][PLOT_VOLTAGE_KEY]},{channels[3][PLOT_CURRENT_KEY]}\n"
            )

    def start_plot(self):
        self.StopFlag = False
        if not self.plot_thread.is_alive():
            self.start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")[:-3]
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
            self.sigInfo.emit("已开启采集")
        else:
            self.sigInfo.emit("采集已开启")
        self.btn_Control(True, True, False, True)

    def close_plot(self):
        self.StopFlag = True
        if self.plot_thread.is_alive():
            self.plot_thread.join()
            self.sigInfo.emit("已关闭采集")
        else:
            self.sigInfo.emit("采集已关闭")
        self.btn_Control(True, True, True, False)

    def checkplot(self):
        return self.plot_thread.is_alive()

    def get_value(self):
        return dict(self.CurrentValues)

    def read_output_snapshot(self):
        snapshot = {}
        for channel in (1, 2, 3):
            voltage = self.gpp.getVoltageOutput(channel)
            current = self.gpp.getCurrentOutput(channel)
            snapshot[channel] = [voltage, current]
            self.CurrentValues[channel] = [voltage, current]
        return snapshot

    def invoke_tcp_power_on(self):
        return self._invoke_in_main_thread(self.output_open_tcp)

    def invoke_tcp_power_off(self):
        return self._invoke_in_main_thread(self.output_close_tcp)

    def invoke_tcp_connect(self):
        return self._invoke_in_main_thread(self.port_open)

    def invoke_tcp_set_voltage(self, channel, voltage):
        return self._invoke_in_main_thread(lambda: self._tcp_set_voltage(channel, voltage))

    def invoke_tcp_set_current(self, channel, current):
        return self._invoke_in_main_thread(lambda: self._tcp_set_current(channel, current))

    def invoke_tcp_get_value(self):
        return self._invoke_in_main_thread(self._tcp_get_value)

    def _tcp_set_voltage(self, channel, voltage):
        if not self.isConnected:
            return [False, "Device not connected"]
        self.V_set(channel, voltage)
        return [True, ""]

    def _tcp_set_current(self, channel, current):
        if not self.isConnected:
            return [False, "Device not connected"]
        self.I_set(channel, current)
        return [True, ""]

    def _tcp_get_value(self):
        if not self.isConnected:
            return [False, "Device not connected"]
        return [True, self.read_output_snapshot()]

    def output_open_tcp(self):
        if not self.isConnected:
            self.sigInfo.emit("请先连接电源")
            return [False, "Device not connected"]
        self.output_open()
        return [True, ""]

    def output_close_tcp(self):
        if not self.isConnected:
            return [False, "Device not connected"]
        self.output_close()
        return [True, ""]

    @classmethod
    def get_instances(cls):
        return cls.instances

    def __del__(self):
        if self in self.instances:
            self.instances.remove(self)
