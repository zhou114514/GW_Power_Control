import configparser
from datetime import datetime
import math
import os
import threading
import time

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QTextCursor

from .MyPlot import MyPlot
from .mu_n_xx_xx import MUNPowerSupply
from .tool import root_path


TOTAL_SEC = 20
TIME_GAP = 25
POINT_NUM = int(100 / TIME_GAP * TOTAL_SEC)
MAX_PLOT_FAILURES = 3
MAX_MUN_CHANNELS = 10
PLOT_VOLTAGE_KEY = "电压"
PLOT_CURRENT_KEY = "电流"
DATA_DIR = os.path.join(".", "电源采集数据")
DEFAULT_VOLTAGE_LIMIT = 100.0
DEFAULT_CURRENT_LIMIT = 100.0


class MUNPower(QtWidgets.QWidget):
    instances = []
    sigInfo = pyqtSignal(str)
    current_warn = pyqtSignal([str, str, str])
    voltage_warn = pyqtSignal([str, str, str])
    structure_changed = pyqtSignal()
    plot_update_signal = pyqtSignal(int, dict)
    _tcp_invoke_signal = pyqtSignal()

    def __init__(self, name, channel_count=3):
        super(MUNPower, self).__init__()
        self.name = name
        self.channel_count = max(2, min(MAX_MUN_CHANNELS, int(channel_count or 3)))
        self.isConnected = False
        self.isOutput = False
        self.StopFlag = True
        self.CurrentValues = {channel: [0.0, 0.0] for channel in range(1, self.channel_count + 1)}
        self.voltage_limits = {channel: DEFAULT_VOLTAGE_LIMIT for channel in range(1, self.channel_count + 1)}
        self.current_limits = {channel: DEFAULT_CURRENT_LIMIT for channel in range(1, self.channel_count + 1)}
        self.mun = MUNPowerSupply(channel_count=self.channel_count)

        self._tcp_invoke_lock = threading.Lock()
        self._tcp_op_event = threading.Event()
        self._tcp_op_func = None
        self._tcp_op_result = None

        self.channel_inputs = {}
        self.channel_outputs = {}
        self.channel_name_edits = {}
        self.channel_plots = {}
        self._signals_bound = False

        self._build_ui()
        self.load_limit_config()
        self._bind_signals()

        self.plot_thread = threading.Thread(target=self.plot_callback)
        self.instances.append(self)
        self.refresh_connection_options(show_message=False)

    def _build_ui(self):
        self.setObjectName(self.name)
        self.resize(1380, 860)
        self.setMinimumSize(1280, 760)

        root = QtWidgets.QGridLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.tabWidget = QtWidgets.QTabWidget(self)
        self.tabWidget.setMinimumWidth(720)
        self.tabWidget.setMaximumWidth(820)

        power_tab = QtWidgets.QWidget()
        power_tab_layout = QtWidgets.QVBoxLayout(power_tab)
        power_tab_layout.setContentsMargins(0, 0, 0, 0)

        power_scroll = QtWidgets.QScrollArea(power_tab)
        power_scroll.setWidgetResizable(True)
        power_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        power_tab_layout.addWidget(power_scroll)

        power_scroll_widget = QtWidgets.QWidget()
        power_scroll.setWidget(power_scroll_widget)

        tab_layout = QtWidgets.QVBoxLayout(power_scroll_widget)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.setSpacing(8)

        title_row = QtWidgets.QHBoxLayout()
        self.portname = QtWidgets.QLabel("串口选择", power_scroll_widget)
        self.powername = QtWidgets.QLabel("", power_scroll_widget)
        title_row.addWidget(self.portname)
        title_row.addWidget(self.powername, 1)
        tab_layout.addLayout(title_row)

        port_row = QtWidgets.QHBoxLayout()
        self.portchoose = QtWidgets.QComboBox(power_scroll_widget)
        self.portcheck = QtWidgets.QPushButton("刷新设备", power_scroll_widget)
        port_row.addWidget(self.portchoose, 1)
        port_row.addWidget(self.portcheck)
        tab_layout.addLayout(port_row)

        self.transport_hint = QtWidgets.QLabel("", power_scroll_widget)
        self.transport_hint.setWordWrap(True)
        tab_layout.addWidget(self.transport_hint)

        port_btn_row = QtWidgets.QHBoxLayout()
        self.portopen = QtWidgets.QPushButton("打开连接", power_scroll_widget)
        self.portclose = QtWidgets.QPushButton("关闭连接", power_scroll_widget)
        port_btn_row.addWidget(self.portopen)
        port_btn_row.addWidget(self.portclose)
        tab_layout.addLayout(port_btn_row)

        tab_layout.addWidget(self._create_line())
        tab_layout.addWidget(self._build_set_group(power_scroll_widget))
        tab_layout.addWidget(self._create_line())
        tab_layout.addWidget(self._build_check_group(power_scroll_widget))
        tab_layout.addWidget(self._create_line())

        self.msg = QtWidgets.QTextEdit(power_scroll_widget)
        self.msg.setReadOnly(True)
        self.msg.setMinimumHeight(180)
        tab_layout.addWidget(self.msg)

        tab_layout.addWidget(self._create_line())

        control_row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("开始输出", power_scroll_widget)
        self.stop_btn = QtWidgets.QPushButton("停止输出", power_scroll_widget)
        control_row.addWidget(self.start_btn)
        control_row.addWidget(self.stop_btn)
        tab_layout.addLayout(control_row)

        listen_row = QtWidgets.QHBoxLayout()
        self.start_listen = QtWidgets.QPushButton("开始采集", power_scroll_widget)
        self.stop_listen = QtWidgets.QPushButton("停止采集", power_scroll_widget)
        listen_row.addWidget(self.start_listen)
        listen_row.addWidget(self.stop_listen)
        tab_layout.addLayout(listen_row)
        tab_layout.addStretch(1)

        self.tabWidget.addTab(power_tab, "电源")

        plot_scroll = QtWidgets.QScrollArea(self)
        plot_scroll.setWidgetResizable(True)
        plot_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        plot_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        plot_widget = QtWidgets.QWidget(plot_scroll)
        plot_layout = QtWidgets.QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(8)
        self.plot_layout = plot_layout
        self.plot_widget = plot_widget

        plot_layout.addStretch(1)
        plot_scroll.setWidget(plot_widget)

        root.addWidget(self.tabWidget, 0, 0)
        root.addWidget(plot_scroll, 0, 1)
        root.setColumnStretch(0, 2)
        root.setColumnStretch(1, 1)

        for channel in range(1, self.channel_count + 1):
            self._append_channel_ui(channel)

        self.refresh_channel_names(use_live_values=False)
        self.btn_Control(False, False, False, False)

    def _build_set_group(self, parent):
        group = QtWidgets.QGroupBox("参数设置 / 保护阈值", parent)
        layout = QtWidgets.QGridLayout(group)
        layout.setColumnStretch(1, 1)
        self.set_group_layout = layout
        self.sendALL = QtWidgets.QPushButton("发送全部数据", group)
        self.add_channel_btn = QtWidgets.QPushButton("增加通道", group)
        layout.addWidget(self.sendALL, 0, 0, 1, 2)
        layout.addWidget(self.add_channel_btn, 0, 2)
        return group

    def _build_check_group(self, parent):
        group = QtWidgets.QGroupBox("输出检查 / 保护阈值", parent)
        layout = QtWidgets.QGridLayout(group)
        layout.setColumnStretch(1, 1)
        self.check_group_layout = layout
        self.checkALL = QtWidgets.QPushButton("检查全部数据", group)
        layout.addWidget(self.checkALL, 0, 0, 1, 3)
        return group

    def _bind_signals(self):
        self.portcheck.clicked.connect(lambda: self.refresh_connection_options(show_message=True))
        self.portopen.clicked.connect(self.power_port_open)
        self.portclose.clicked.connect(self.power_port_close)
        self.sendALL.clicked.connect(self.sendALLData)
        self.checkALL.clicked.connect(self.checkALLData)
        self.add_channel_btn.clicked.connect(self.add_channel)
        self.start_btn.clicked.connect(self.output_open)
        self.stop_btn.clicked.connect(self.output_close)
        self.start_listen.clicked.connect(self.start_plot)
        self.stop_listen.clicked.connect(self.close_plot)

        for channel in range(1, self.channel_count + 1):
            self._bind_channel_signals(channel)

        self.sigInfo.connect(self.show_msg)
        self.plot_update_signal.connect(self._on_plot_update)
        self._tcp_invoke_signal.connect(self._on_tcp_invoke)
        self._signals_bound = True

    def _append_channel_ui(self, channel):
        self._append_set_channel_ui(channel)
        self._append_check_channel_ui(channel)
        self._append_plot_channel_ui(channel)
        self._reposition_group_buttons()

    def _append_set_channel_ui(self, channel):
        base_row = (channel - 1) * 4
        voltage_input = QtWidgets.QLineEdit(self.sendALL.parent())
        current_input = QtWidgets.QLineEdit(self.sendALL.parent())
        voltage_limit_input = QtWidgets.QLineEdit(self.sendALL.parent())
        limit_input = QtWidgets.QLineEdit(self.sendALL.parent())
        voltage_input.setText("5.00")
        current_input.setText("1.00")
        voltage_limit_input.setText(f"{self.voltage_limits[channel]:.3f}")
        limit_input.setText(f"{self.current_limits[channel]:.3f}")

        voltage_send = QtWidgets.QPushButton("发送", self.sendALL.parent())
        current_send = QtWidgets.QPushButton("发送", self.sendALL.parent())
        voltage_limit_send = QtWidgets.QPushButton("发送", self.sendALL.parent())
        limit_send = QtWidgets.QPushButton("发送", self.sendALL.parent())

        self.set_group_layout.addWidget(QtWidgets.QLabel(f"CH{channel} 电压(V)", self.sendALL.parent()), base_row, 0)
        self.set_group_layout.addWidget(voltage_input, base_row, 1)
        self.set_group_layout.addWidget(voltage_send, base_row, 2)

        self.set_group_layout.addWidget(QtWidgets.QLabel(f"CH{channel} 电流(A)", self.sendALL.parent()), base_row + 1, 0)
        self.set_group_layout.addWidget(current_input, base_row + 1, 1)
        self.set_group_layout.addWidget(current_send, base_row + 1, 2)

        self.set_group_layout.addWidget(
            QtWidgets.QLabel(f"CH{channel} 硬件保护电压阈值(V)", self.sendALL.parent()),
            base_row + 2,
            0,
        )
        self.set_group_layout.addWidget(voltage_limit_input, base_row + 2, 1)
        self.set_group_layout.addWidget(voltage_limit_send, base_row + 2, 2)

        self.set_group_layout.addWidget(
            QtWidgets.QLabel(f"CH{channel} 硬件保护电流阈值(A)", self.sendALL.parent()),
            base_row + 3,
            0,
        )
        self.set_group_layout.addWidget(limit_input, base_row + 3, 1)
        self.set_group_layout.addWidget(limit_send, base_row + 3, 2)

        self.channel_inputs[channel] = {
            "voltage": voltage_input,
            "current": current_input,
            "voltage_limit": voltage_limit_input,
            "limit": limit_input,
            "voltage_send": voltage_send,
            "current_send": current_send,
            "voltage_limit_send": voltage_limit_send,
            "limit_send": limit_send,
        }

    def _append_check_channel_ui(self, channel):
        base_row = (channel - 1) * 4
        voltage_print = self._create_display_edit(self.checkALL.parent())
        current_print = self._create_display_edit(self.checkALL.parent())
        voltage_limit_print = self._create_display_edit(self.checkALL.parent())
        limit_print = self._create_display_edit(self.checkALL.parent())
        voltage_check = QtWidgets.QPushButton("读取", self.checkALL.parent())
        current_check = QtWidgets.QPushButton("读取", self.checkALL.parent())
        voltage_limit_check = QtWidgets.QPushButton("本地读取", self.checkALL.parent())
        limit_check = QtWidgets.QPushButton("本地读取", self.checkALL.parent())

        self.check_group_layout.addWidget(voltage_print, base_row, 0, 1, 2)
        self.check_group_layout.addWidget(voltage_check, base_row, 2)
        self.check_group_layout.addWidget(current_print, base_row + 1, 0, 1, 2)
        self.check_group_layout.addWidget(current_check, base_row + 1, 2)
        self.check_group_layout.addWidget(voltage_limit_print, base_row + 2, 0, 1, 2)
        self.check_group_layout.addWidget(voltage_limit_check, base_row + 2, 2)
        self.check_group_layout.addWidget(limit_print, base_row + 3, 0, 1, 2)
        self.check_group_layout.addWidget(limit_check, base_row + 3, 2)

        self.channel_outputs[channel] = {
            "voltage": voltage_print,
            "current": current_print,
            "voltage_limit": voltage_limit_print,
            "limit": limit_print,
            "voltage_check": voltage_check,
            "current_check": current_check,
            "voltage_limit_check": voltage_limit_check,
            "limit_check": limit_check,
        }

    def _append_plot_channel_ui(self, channel):
        name_edit = QtWidgets.QLineEdit(f"CH{channel}", self.plot_widget)
        name_edit.setReadOnly(True)
        plot = MyPlot(
            dataDict={PLOT_VOLTAGE_KEY: [], PLOT_CURRENT_KEY: []},
            dataLen=POINT_NUM,
        )
        insert_index = max(self.plot_layout.count() - 1, 0)
        self.plot_layout.insertWidget(insert_index, name_edit)
        self.plot_layout.insertWidget(insert_index + 1, plot)
        self.channel_name_edits[channel] = name_edit
        self.channel_plots[channel] = plot

    def _reposition_group_buttons(self):
        action_row = self.channel_count * 4
        self.set_group_layout.removeWidget(self.sendALL)
        self.set_group_layout.removeWidget(self.add_channel_btn)
        self.check_group_layout.removeWidget(self.checkALL)
        self.set_group_layout.addWidget(self.sendALL, action_row, 0, 1, 2)
        self.set_group_layout.addWidget(self.add_channel_btn, action_row, 2)
        self.check_group_layout.addWidget(self.checkALL, action_row, 0, 1, 3)

    def _bind_channel_signals(self, channel):
        self.channel_inputs[channel]["voltage_send"].clicked.connect(
            lambda checked=False, ch=channel: self.V_set(ch)
        )
        self.channel_inputs[channel]["current_send"].clicked.connect(
            lambda checked=False, ch=channel: self.I_set(ch)
        )
        self.channel_inputs[channel]["voltage_limit_send"].clicked.connect(
            lambda checked=False, ch=channel: self.voltage_limit_set(ch)
        )
        self.channel_inputs[channel]["limit_send"].clicked.connect(
            lambda checked=False, ch=channel: self.limit_set(ch)
        )
        self.channel_outputs[channel]["voltage_check"].clicked.connect(
            lambda checked=False, ch=channel: self.V_get(ch)
        )
        self.channel_outputs[channel]["current_check"].clicked.connect(
            lambda checked=False, ch=channel: self.I_get(ch)
        )
        self.channel_outputs[channel]["voltage_limit_check"].clicked.connect(
            lambda checked=False, ch=channel: self.voltage_limit_get(ch)
        )
        self.channel_outputs[channel]["limit_check"].clicked.connect(
            lambda checked=False, ch=channel: self.limit_get(ch)
        )

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
        resources = MUNPowerSupply.list_available_resources()
        self.portchoose.clear()
        for resource in resources:
            self.portchoose.addItem(resource)

        if current_resource and current_resource in resources:
            self.portchoose.setCurrentText(current_resource)
        elif resources:
            self.portchoose.setCurrentIndex(0)

        hint = MUNPowerSupply.get_environment_hint()
        self.transport_hint.setText(hint)
        if hint:
            self.sigInfo.emit(hint)

        if show_message:
            if resources:
                QtWidgets.QMessageBox.information(self, "提示", f"检测到 {len(resources)} 个可用串口")
            else:
                QtWidgets.QMessageBox.warning(self, "提示", hint or "未检测到可用设备")

        return resources

    def show_msg(self, info):
        self.msg.moveCursor(QTextCursor.End)
        self.msg.insertPlainText(f"{info}\n")

    def refresh_channel_names(self, use_live_values=True):
        self.powername.setText(self.mun.get_idn())
        for channel in self._visible_channels():
            if use_live_values and self.isConnected:
                voltage = self.mun.getVoltage(channel)
                current = self.mun.getCurrent(channel)
            else:
                voltage = float(self.channel_inputs[channel]["voltage"].text())
                current = float(self.channel_inputs[channel]["current"].text())
            self.channel_name_edits[channel].setText(f"CH{channel}：{voltage:.3f}V / {current:.3f}A")

    def _get_limit_config_path(self):
        return os.path.join(root_path, "Auto_config.ini")

    def _get_limit_section_name(self):
        return f"MU_N_LIMITS:{self.name}"

    def _visible_channels(self):
        return range(1, self.channel_count + 1)

    def export_limit_settings(self):
        settings = {}
        for channel in self._visible_channels():
            settings[f"voltage_{channel}"] = f"{self._get_voltage_limit_value(channel):.3f}"
            settings[f"current_{channel}"] = f"{self._get_current_limit_value(channel):.3f}"
        return settings

    def _set_voltage_limit_value(self, channel, value, update_input=True):
        value = self._normalize_voltage_limit_value(value)
        self.voltage_limits[channel] = value
        if update_input:
            self.channel_inputs[channel]["voltage_limit"].setText(f"{value:.3f}")

    def _get_voltage_limit_value(self, channel):
        value = self._normalize_voltage_limit_value(
            self.voltage_limits.get(channel, DEFAULT_VOLTAGE_LIMIT),
            fallback=DEFAULT_VOLTAGE_LIMIT,
        )
        self.voltage_limits[channel] = value
        return value

    def _set_limit_value(self, channel, value, update_input=True):
        value = self._normalize_current_limit_value(value)
        self.current_limits[channel] = value
        if update_input:
            self.channel_inputs[channel]["limit"].setText(f"{value:.3f}")

    def _get_current_limit_value(self, channel):
        value = self._normalize_current_limit_value(
            self.current_limits.get(channel, DEFAULT_CURRENT_LIMIT),
            fallback=DEFAULT_CURRENT_LIMIT,
        )
        self.current_limits[channel] = value
        return value

    def _get_limit_value(self, channel):
        return self._get_current_limit_value(channel)

    def _normalize_voltage_limit_value(self, value, fallback=None):
        try:
            limit_value = float(value)
        except Exception:
            if fallback is not None:
                return float(fallback)
            raise ValueError("Software voltage limit must be a finite non-negative number")

        if math.isfinite(limit_value) and limit_value >= 0:
            return limit_value

        if fallback is not None:
            return float(fallback)

        raise ValueError("Software voltage limit must be a finite non-negative number")

    def _normalize_current_limit_value(self, value, fallback=None):
        try:
            limit_value = float(value)
        except Exception:
            if fallback is not None:
                return float(fallback)
            raise ValueError("Software current limit must be a finite non-negative number")

        if math.isfinite(limit_value) and limit_value >= 0:
            return limit_value

        if fallback is not None:
            return float(fallback)

        raise ValueError("Software current limit must be a finite non-negative number")

    def load_limit_config(self):
        config = configparser.ConfigParser()
        config.read(self._get_limit_config_path(), encoding="utf-8")
        section_name = self._get_limit_section_name()
        for channel in self._visible_channels():
            voltage_value = DEFAULT_VOLTAGE_LIMIT
            current_value = DEFAULT_CURRENT_LIMIT
            if config.has_section(section_name):
                try:
                    raw_voltage_value = config.get(
                        section_name,
                        f"voltage_{channel}",
                        fallback=str(DEFAULT_VOLTAGE_LIMIT),
                    )
                    voltage_value = self._normalize_voltage_limit_value(
                        raw_voltage_value,
                        fallback=DEFAULT_VOLTAGE_LIMIT,
                    )
                except Exception:
                    voltage_value = DEFAULT_VOLTAGE_LIMIT
                try:
                    raw_current_value = config.get(
                        section_name,
                        f"current_{channel}",
                        fallback=config.get(section_name, f"channel_{channel}", fallback=str(DEFAULT_CURRENT_LIMIT)),
                    )
                    current_value = self._normalize_current_limit_value(
                        raw_current_value,
                        fallback=DEFAULT_CURRENT_LIMIT,
                    )
                except Exception:
                    current_value = DEFAULT_CURRENT_LIMIT
            self._set_voltage_limit_value(channel, voltage_value)
            self._set_limit_value(channel, current_value)

    def persist_limit_config(self):
        config = configparser.ConfigParser()
        config.read(self._get_limit_config_path(), encoding="utf-8")
        section_name = self._get_limit_section_name()
        if not config.has_section(section_name):
            config.add_section(section_name)
        for channel in range(1, 11):
            config.remove_option(section_name, f"channel_{channel}")
            config.remove_option(section_name, f"voltage_{channel}")
            config.remove_option(section_name, f"current_{channel}")
        for option, value in self.export_limit_settings().items():
            config.set(section_name, option, value)
        with open(self._get_limit_config_path(), "w", encoding="utf-8") as f:
            config.write(f)

    def _rebuild_driver(self, new_channel_count):
        was_connected = self.isConnected
        resource_name = self.portchoose.currentText().strip() if was_connected else ""
        old_driver = self.mun
        old_channel_count = getattr(old_driver, "channel_count", self.channel_count)
        if was_connected:
            try:
                old_driver.close()
            except Exception:
                pass

        new_driver = MUNPowerSupply(channel_count=new_channel_count)

        if was_connected and resource_name:
            try:
                new_driver.open(resource_name)
                self.mun = new_driver
                self.isConnected = True
                return True
            except Exception as e:
                self.isConnected = False
                self.sigInfo.emit(f"通道结构已更新，但重新连接设备失败：{e}")

                restored_driver = MUNPowerSupply(channel_count=old_channel_count)
                restore_ok = False
                try:
                    restored_driver.open(resource_name)
                    restore_ok = True
                except Exception:
                    pass
                self.mun = restored_driver if restore_ok else new_driver
                self.isConnected = restore_ok
                self.sigInfo.emit(f"閫氶亾缁撴瀯鏇存柊澶辫触锛岄噸鏂拌繛鎺ヨ澶囧け璐ワ細{e}")
                return False

        self.mun = new_driver
        self.isConnected = False
        return True

    def _best_effort_disable_hidden_channels(self):
        original_count = getattr(self.mun, "channel_count", self.channel_count)
        try:
            self.mun.channel_count = MAX_MUN_CHANNELS
            for channel in range(self.channel_count + 1, MAX_MUN_CHANNELS + 1):
                try:
                    self.mun.enableOutput(False, channel)
                except Exception:
                    break
        finally:
            self.mun.channel_count = original_count

    def _set_visible_outputs(self, enable):
        if enable:
            self._best_effort_disable_hidden_channels()
            for channel in self._visible_channels():
                self.mun.enableOutput(True, channel)
            return

        for channel in self._visible_channels():
            self.mun.enableOutput(False, channel)
        self.mun.enableOutput(False)

    def add_channel(self):
        if self.isOutput:
            QtWidgets.QMessageBox.warning(self, "提示", "输出开启时不能增加通道")
            return
        if self.plot_thread.is_alive():
            QtWidgets.QMessageBox.warning(self, "提示", "采集开启时不能增加通道")
            return
        if self.channel_count >= MAX_MUN_CHANNELS:
            QtWidgets.QMessageBox.warning(self, "提示", "MU_N 最多支持 10 个通道")
            return

        new_channel = self.channel_count + 1
        if not self._rebuild_driver(new_channel):
            QtWidgets.QMessageBox.warning(self, "鎻愮ず", "澧炲姞閫氶亾澶辫触锛岃妫€鏌ヨ澶囪繛鎺ュ悗閲嶈瘯")
            return
        self.CurrentValues[new_channel] = [0.0, 0.0]
        self.voltage_limits[new_channel] = DEFAULT_VOLTAGE_LIMIT
        self.current_limits[new_channel] = DEFAULT_CURRENT_LIMIT
        self.channel_count = new_channel

        self._append_channel_ui(new_channel)
        if self._signals_bound:
            self._bind_channel_signals(new_channel)

        self.persist_limit_config()
        self.refresh_channel_names(use_live_values=self.isConnected)
        self.structure_changed.emit()
        self.sigInfo.emit(f"已增加 CH{new_channel}，当前共 {self.channel_count} 个通道")

    def _on_plot_update(self, channel, data):
        self.channel_plots[channel].updateData(data)

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

    def power_port_open(self):
        result = self.port_open()
        if result[0]:
            QtWidgets.QMessageBox.information(self, "提示", f"已连接 {self.portchoose.currentText()}\n{result[1]}")
        else:
            QtWidgets.QMessageBox.warning(self, "错误", result[1] if len(result) > 1 else "连接失败")

    def port_open(self, show_error=True):
        resource_name = self.portchoose.currentText().strip()
        if not resource_name:
            hint = MUNPowerSupply.get_environment_hint() or "未检测到可用设备"
            if show_error:
                QtWidgets.QMessageBox.warning(self, "错误", hint)
            return [False, hint]

        if self.isConnected:
            self.sigInfo.emit(f"已连接{resource_name}")
            return [True, self.powername.text()]

        try:
            self.mun.open(resource_name)
            self.isConnected = True
            self.refresh_channel_names()
            self.sigInfo.emit(f"已连接{resource_name}")
            self.btn_Control(True, False, False, False)
            return [True, self.powername.text()]
        except Exception as e:
            try:
                self.mun.close()
            except Exception:
                pass
            self.isConnected = False
            if show_error:
                QtWidgets.QMessageBox.warning(self, "错误", f"连接 {resource_name} 失败：{e}")
            return [False, str(e)]

    def startup_port_open(self):
        return self.port_open(show_error=False)

    def power_port_close(self):
        if self.plot_thread.is_alive():
            self.close_plot()
        try:
            self.mun.close()
        finally:
            self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
            self.isConnected = False
            self.isOutput = False
            self.btn_Control(False, False, False, False)

    def V_set(self, channel, voltage=None):
        if voltage is None:
            voltage = float(self.channel_inputs[channel]["voltage"].text())
        self.mun.setVoltage(channel, voltage)
        self.sigInfo.emit(f"已设置CH{channel}通道电压为{float(voltage):.3f}V")
        self.refresh_channel_names()
        return float(voltage)

    def I_set(self, channel, current=None):
        if current is None:
            current = float(self.channel_inputs[channel]["current"].text())
        self.mun.setCurrent(channel, current)
        self.sigInfo.emit(f"已设置CH{channel}通道电流为{float(current):.3f}A")
        self.refresh_channel_names()
        return float(current)

    def limit_set(self, channel, current_limit=None):
        if current_limit is None:
            current_limit = float(self.channel_inputs[channel]["limit"].text())
        self._set_limit_value(channel, current_limit)
        if self.isConnected:
            self.mun.setCurrentLimit(channel, current_limit)
        self.persist_limit_config()
        value = self._get_current_limit_value(channel)
        self.channel_outputs[channel]["limit"].setText(f"硬件保护阈值电流：{value:.3f}A")
        if self.isConnected:
            self.sigInfo.emit(f"已设置CH{channel}硬件保护电流阈值为{value:.3f}A")
        else:
            self.sigInfo.emit(
                f"已保存CH{channel}硬件保护电流阈值为{value:.3f}A，连接设备后发送或启动输出时会下发"
            )
        return float(current_limit)

    def voltage_limit_set(self, channel, voltage_limit=None):
        if voltage_limit is None:
            voltage_limit = float(self.channel_inputs[channel]["voltage_limit"].text())
        self._set_voltage_limit_value(channel, voltage_limit)
        if self.isConnected:
            self.mun.setVoltageLimit(channel, voltage_limit)
        self.persist_limit_config()
        value = self._get_voltage_limit_value(channel)
        self.channel_outputs[channel]["voltage_limit"].setText(f"硬件保护阈值电压：{value:.3f}V")
        if self.isConnected:
            self.sigInfo.emit(f"已设置CH{channel}硬件保护电压阈值为{value:.3f}V")
        else:
            self.sigInfo.emit(
                f"已保存CH{channel}硬件保护电压阈值为{value:.3f}V，连接设备后发送或启动输出时会下发"
            )
        return float(voltage_limit)

    def sendALLData(self):
        for channel in self._visible_channels():
            self.V_set(channel)
            self.I_set(channel)
            self.voltage_limit_set(channel)
            self.limit_set(channel)
        self.sigInfo.emit("已下发全部电压/电流参数，并同步保护电压/电流阈值到硬件")

    def V_get(self, channel):
        value = self.mun.getVoltageOutput(channel)
        self.channel_outputs[channel]["voltage"].setText(f"电压：{value:.3f}")
        return value

    def I_get(self, channel):
        value = self.mun.getCurrentOutput(channel)
        self.channel_outputs[channel]["current"].setText(f"电流：{value:.3f}")
        return value

    def limit_get(self, channel):
        if self.isConnected:
            value = self.mun.getCurrentLimit(channel)
            self._set_limit_value(channel, value)
        else:
            value = self._get_current_limit_value(channel)
        self.channel_outputs[channel]["limit"].setText(f"硬件保护阈值电流：{value:.3f}A")
        return value

    def voltage_limit_get(self, channel):
        if self.isConnected:
            value = self.mun.getVoltageLimit(channel)
            self._set_voltage_limit_value(channel, value)
        else:
            value = self._get_voltage_limit_value(channel)
        self.channel_outputs[channel]["voltage_limit"].setText(f"硬件保护阈值电压：{value:.3f}V")
        return value

    def checkALLData(self):
        data = [[]]
        for channel in self._visible_channels():
            voltage = self.V_get(channel)
            current = self.I_get(channel)
            voltage_limit = self.voltage_limit_get(channel)
            current_limit = self.limit_get(channel)
            data[0].append(f"{voltage:.3f}")
            data[0].append(f"{current:.3f}")
            data[0].append(f"{voltage_limit:.3f}")
            data[0].append(f"{current_limit:.3f}")
        return data

    def output_open(self):
        if not self.isConnected:
            self.sigInfo.emit("请先连接电源")
            return
        if self.isOutput:
            self.sigInfo.emit("电源输出已开启")
            return

        self.sendALLData()
        self._set_visible_outputs(True)
        time.sleep(0.3)
        self.sigInfo.emit("已打开电源输出")
        self.isOutput = True
        self.btn_Control(False, True, False, True)
        self.start_plot()

    def output_close(self):
        if not self.isConnected:
            self.sigInfo.emit("请先连接电源")
            return
        if not self.isOutput:
            self.sigInfo.emit("电源输出已关闭")
            self.btn_Control(True, False, False, False)
            return

        try:
            self._set_visible_outputs(False)
        finally:
            self.sigInfo.emit("已关闭电源输出")
            self.isOutput = False
            if self.plot_thread.is_alive():
                self.StopFlag = True
                self.plot_thread.join()
            self.btn_Control(True, False, False, False)

    def plot_callback(self):
        channels = {
            channel: {PLOT_VOLTAGE_KEY: 0.0, PLOT_CURRENT_KEY: 0.0}
            for channel in self._visible_channels()
        }
        fail_count = 0

        while not self.StopFlag:
            try:
                values = self.mun.getOutput()
                fail_count = 0

                for index, channel in enumerate(self._visible_channels()):
                    voltage, current = values[index]
                    channels[channel][PLOT_VOLTAGE_KEY] = voltage
                    channels[channel][PLOT_CURRENT_KEY] = current
                    self.CurrentValues[channel] = [voltage, current]

                    self.plot_update_signal.emit(channel, dict(channels[channel]))

                    voltage_limit = self._get_voltage_limit_value(channel)
                    if voltage_limit > 0 and voltage >= voltage_limit:
                        try:
                            self._set_visible_outputs(False)
                        except Exception:
                            pass
                        self.StopFlag = True
                        self.isOutput = False
                        self.voltage_warn.emit(self.name, f"CH{channel}", f"{voltage:.3f}")
                        self.sigInfo.emit(
                            f"CH{channel}电压达到保护阈值 {voltage_limit:.3f}V，已停止输出"
                        )
                        break

                    current_limit = self._get_current_limit_value(channel)
                    if current_limit > 0 and current >= current_limit:
                        try:
                            self._set_visible_outputs(False)
                        except Exception:
                            pass
                        self.StopFlag = True
                        self.isOutput = False
                        self.current_warn.emit(self.name, f"CH{channel}", f"{current:.3f}")
                        self.sigInfo.emit(
                            f"CH{channel}电流达到保护阈值 {current_limit:.3f}A，已停止输出"
                        )
                        break

                if self.StopFlag:
                    break

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
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(DATA_DIR, f"{self.name}_{self.start_time}.csv")

        if not os.path.exists(file_path):
            headers = ["时间"]
            for channel in self._visible_channels():
                headers.extend([f"CH{channel}电压", f"CH{channel}电流"])
            with open(file_path, "w", encoding="gbk") as f:
                f.write(",".join(headers) + "\n")

        row = [datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]]
        for channel in self._visible_channels():
            row.append(str(channels[channel][PLOT_VOLTAGE_KEY]))
            row.append(str(channels[channel][PLOT_CURRENT_KEY]))

        with open(file_path, "a", encoding="gbk") as f:
            f.write(",".join(row) + "\n")

    def start_plot(self):
        self.StopFlag = False
        if not self.plot_thread.is_alive():
            self.start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")[:-3]
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
            self.sigInfo.emit("已开启采集")
        else:
            self.sigInfo.emit("采集已开启")
        self.btn_Control(False if self.isOutput else True, True if self.isOutput else False, False, True)

    def close_plot(self):
        self.StopFlag = True
        if self.plot_thread.is_alive():
            self.plot_thread.join()
            self.sigInfo.emit("已关闭采集")
        else:
            self.sigInfo.emit("采集已关闭")
        self.btn_Control(True, self.isOutput, False, False)

    def checkplot(self):
        return self.plot_thread.is_alive()

    def get_value(self):
        return dict(self.CurrentValues)

    def read_output_snapshot(self):
        snapshot = {}
        for channel in self._visible_channels():
            voltage = self.mun.getVoltageOutput(channel)
            current = self.mun.getCurrentOutput(channel)
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
