# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import binascii
import pandas as pd
from PyQt5 import QtGui
# C:\Python\Python36\Scripts\pyinstaller.exe -F --noconsole --onefile -p D:\Coding\python\Pyserial-Demo-master\venv\Lib\site-packages pyserial_demo_2.py
import os.path

from Utility.MainWindow.MainWindow import Ui_MainWindow

from .方形电源控制 import SquarePower
from .长条电源控制 import LongPower
from .GPP电源控制 import GPPPower
from .MU_N电源控制 import MUNPower
# from .TCP import TCP
from .TCPServer import TCPServer
from .tool import *
from .FTP import FTPClient
from .alarm_player import AlarmPlayer
from .update_checker import UpdateCheckThread
from .update_installer import launch_update_installer
from .version_control import get_about_html, get_current_version
import configparser
import json

VERSION = get_current_version()
DEFAULT_POWER_ITEMS = [
    {"name": "方形电源", "type": "GPW", "serial_key": "power_supply_square1"},
    {"name": "方形2", "type": "GPW", "serial_key": "power_supply_square2"},
    {"name": "方形3", "type": "GPW", "serial_key": "power_supply_square3"},
    {"name": "长条电源", "type": "PSW", "serial_key": "power_supply_long"},
    {"name": "GPP", "type": "GPP", "serial_key": "power_supply_gpp"},
]


class AddPowerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AddPowerDialog, self).__init__(parent)
        self.setWindowTitle("添加电源")
        self.setModal(True)
        self.resize(340, 200)

        layout = QtWidgets.QVBoxLayout(self)
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.setLabelAlignment(QtCore.Qt.AlignRight)

        self.power_type = QtWidgets.QComboBox(self)
        self.power_type.addItems(["GPW", "PSW", "GPP", "MU_N"])
        self.form_layout.addRow("电源类型：", self.power_type)

        self.power_name = QtWidgets.QLineEdit(self)
        self.power_name.setPlaceholderText("请输入电源名称")
        self.form_layout.addRow("电源名称：", self.power_name)

        self.channel_count_label = QtWidgets.QLabel("通道数：", self)
        self.channel_count = QtWidgets.QSpinBox(self)
        self.channel_count.setRange(2, 10)
        self.channel_count.setValue(3)
        self.form_layout.addRow(self.channel_count_label, self.channel_count)
        layout.addLayout(self.form_layout)

        button_box = QtWidgets.QDialogButtonBox(self)
        self.confirm_button = button_box.addButton("确认", QtWidgets.QDialogButtonBox.AcceptRole)
        button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        self.confirm_button.clicked.connect(self._accept_if_valid)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.power_type.currentTextChanged.connect(self._update_dynamic_fields)
        self._update_dynamic_fields()

    def _accept_if_valid(self):
        if not self.get_power_name():
            QtWidgets.QMessageBox.warning(self, "提示", "请输入电源名称")
            return
        self.accept()

    def get_power_type(self):
        return self.power_type.currentText()

    def get_power_name(self):
        return self.power_name.text().strip()

    def get_channel_count(self):
        return self.channel_count.value()

    def _update_dynamic_fields(self):
        is_mun = self.get_power_type() == "MU_N"
        self.channel_count_label.setVisible(is_mun)
        self.channel_count.setVisible(is_mun)


class UpperPcWin(QtWidgets.QMainWindow,Ui_MainWindow):  # 主窗口只负责处理左侧按钮弹出窗口的逻辑
    leftBtnDict = {}  # 左侧按钮
    bindBtnWidget={}  # 右侧页面
    rightPageDict = {}
    portObjs={}
    istestData=False  # 是否测试数据
    # myWidgetObj=None  # 必须在 show 以后运行
    def __init__(self):
        super(UpperPcWin, self).__init__()
        self.setupUi(self)  # 必须放在 show 之后
        self.added_power_widgets = {}  # {name: widget_obj}
        self.default_power_items = []
        self.default_power_widgets = []
        self.default_power_widget_items = []
        self.power_control_obj1 = None
        self.power_control_obj5 = None
        self.power_control_obj_gpp = None
        self.initial_button_name = None
        self.startup_square_notified = False
        self.startup_long_notified = False
        self.startup_gpp_notified = False
        self.startup_auto_output_done = False
        self.version_about_dialog = None
        self.update_check_thread = None
        self.is_updating = False
        self.tcp_server = None
        self.alarm_player = AlarmPlayer()
        self.adjustStartupWindow()
        self.setWindowTitle(f"[SRC] 光学头电源控制 {VERSION}")
        # self.ftp = FTPClient("192.168.10.100", "yab", "qwer1234!!")

        # self.initData()

    def initUi(self):  # 子页面需要的 ContextInfo 通过名称联系起来
        self.label.setText(VERSION)
        self.label.clicked.connect(self.openVersionAboutDialog)

        # 删除所有左侧按钮
        self.leftlayout = QGridLayout()

        self.addGlobalControlButtons()
        self.addBTN()
        self.delBTN()

        self.loadDefaultPowerWidgets()
        self.loadPersistedAddedPowers()
        self.applyConfiguredPorts()
        self.applySafetyConfig()
        self.refreshTotalControlSummary()
        if "Btn总控" in self.leftBtnDict:
            self.leftBtnCallback("Btn总控")

        # self.tcp = TCP("TCP")
        self.tcp_server = TCPServer()
        self.tcp_server.start()

        self.adjustStartupWindow()
        # QtCore.QTimer.singleShot(1000, self.runStartupDetection)
        # QtCore.QTimer.singleShot(1500, self.checkUpdateOnStartup)

    def getGlobalControlButtonStyle(self):
        return (
            "QPushButton {"
            "font: 75 12pt \"微软雅黑\";"
            "color: #ffffff;"
            "background-color: #1769aa;"
            "border: 1px solid #0d4f82;"
            "border-radius: 6px;"
            "padding: 9px 12px;"
            "min-height: 38px;"
            "}"
            "QPushButton:hover {"
            "background-color: #1f7fc8;"
            "}"
            "QPushButton:pressed {"
            "background-color: #0b4d80;"
            "}"
            "QPushButton:disabled {"
            "background-color: #8ea4b5;"
            "border-color: #7b8c9a;"
            "}"
        )

    def addGlobalControlButtons(self):
        BtnCustom = QtWidgets.QPushButton(self.frame_left)
        BtnCustom.setStyleSheet(self.getPowerButtonStyle())
        BtnCustom.setCheckable(True)
        BtnCustom.setObjectName("Btn总控")
        BtnCustom.setText("总控")
        self.leftlayout.addWidget(BtnCustom, self.leftlayout.count(), 0)
        self.frame_left.setLayout(self.leftlayout)

        page_custom = self.createTotalControlPage()
        page_custom.setObjectName("Page总控")
        self.stackedWidget.addWidget(page_custom)

        self.bindBtnWidget[BtnCustom.objectName()] = page_custom.objectName()
        self.leftBtnDict[BtnCustom.objectName()] = BtnCustom
        self.rightPageDict[BtnCustom.objectName()] = page_custom

        BtnCustom.clicked.connect(lambda: self.leftBtnCallback(BtnCustom.objectName()))

    def createTotalControlPage(self):
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        action_widget = QtWidgets.QWidget(page)
        action_layout = QtWidgets.QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(14)

        actions = [
            ("oneKeyConnectBtn", "一键连接", self.oneKeyConnect),
            ("oneKeyPowerOnBtn", "一键上电", self.oneKeyPowerOn),
            ("oneKeyPowerOffBtn", "一键下电", self.oneKeyPowerOff),
        ]
        self.global_control_buttons = []
        for object_name, text, callback in actions:
            button = QtWidgets.QPushButton(action_widget)
            button.setObjectName(object_name)
            button.setText(text)
            button.setStyleSheet(self.getGlobalControlButtonStyle())
            button.setMinimumHeight(72)
            button.clicked.connect(callback)
            action_layout.addWidget(button)
            self.global_control_buttons.append(button)

        summary_widget = QtWidgets.QWidget(page)
        summary_layout = QtWidgets.QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)

        summary_title = QtWidgets.QLabel("默认电源通道预设与连接资源", summary_widget)
        summary_title.setStyleSheet("font: 75 12pt \"微软雅黑\"; color: #1f2d3d;")
        summary_layout.addWidget(summary_title)

        self.total_summary_table = QtWidgets.QTableWidget(0, 6, summary_widget)
        self.total_summary_table.setHorizontalHeaderLabels(
            ["电源名称", "型号", "通道", "预设电压(V)", "预设电流(A)", "串口/资源"]
        )
        self.total_summary_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.total_summary_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.total_summary_table.setAlternatingRowColors(True)
        self.total_summary_table.verticalHeader().setVisible(False)
        self.total_summary_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        summary_layout.addWidget(self.total_summary_table)

        root.addWidget(action_widget)
        root.addWidget(summary_widget)
        root.setStretch(0, 1)
        root.setStretch(1, 2)
        return page

    def _read_control_text(self, control, default="-"):
        if control is None:
            return default
        try:
            if hasattr(control, "currentText"):
                value = control.currentText()
            else:
                value = control.text()
        except Exception:
            return default

        value = str(value).strip()
        return value if value else default

    def _get_widget_resource_text(self, widget_obj):
        if not hasattr(widget_obj, "portchoose"):
            return "-"
        return self._read_control_text(widget_obj.portchoose)

    def _get_widget_type_label(self, widget_obj):
        if isinstance(widget_obj, SquarePower):
            return "GPW"
        if isinstance(widget_obj, LongPower):
            return "长条"
        if isinstance(widget_obj, GPPPower):
            return "GPP"
        if isinstance(widget_obj, MUNPower):
            return "MU_N"
        return "-"

    def _build_total_summary_rows(self):
        rows = []
        for widget_obj in self.default_power_widgets:
            power_name = getattr(widget_obj, "name", "-")
            power_type = self._get_widget_type_label(widget_obj)
            resource = self._get_widget_resource_text(widget_obj)

            if isinstance(widget_obj, SquarePower):
                rows.append([
                    power_name,
                    power_type,
                    "CH1",
                    self._read_control_text(getattr(widget_obj, "CH1_V", None)),
                    self._read_control_text(getattr(widget_obj, "CH1_I", None)),
                    resource,
                ])
                rows.append([
                    power_name,
                    power_type,
                    "CH2",
                    self._read_control_text(getattr(widget_obj, "CH2_V", None)),
                    self._read_control_text(getattr(widget_obj, "CH2_I", None)),
                    resource,
                ])
            elif isinstance(widget_obj, LongPower):
                rows.append([
                    power_name,
                    power_type,
                    "CH1",
                    self._read_control_text(getattr(widget_obj, "CH1_V", None)),
                    self._read_control_text(getattr(widget_obj, "CH1_I", None)),
                    resource,
                ])
            elif isinstance(widget_obj, GPPPower):
                rows.append([
                    power_name,
                    power_type,
                    "CH1",
                    self._read_control_text(getattr(widget_obj, "CH1_V", None)),
                    self._read_control_text(getattr(widget_obj, "CH1_I", None)),
                    resource,
                ])
                rows.append([
                    power_name,
                    power_type,
                    "CH2",
                    self._read_control_text(getattr(widget_obj, "CH2_V", None)),
                    self._read_control_text(getattr(widget_obj, "CH2_I", None)),
                    resource,
                ])
                rows.append([
                    power_name,
                    power_type,
                    "CH3",
                    self._read_control_text(getattr(widget_obj, "CH3_V", None)),
                    "5.0",
                    resource,
                ])
        return rows

    def refreshTotalControlSummary(self):
        table = getattr(self, "total_summary_table", None)
        if table is None:
            return

        rows = self._build_total_summary_rows()
        table.setRowCount(len(rows))
        for row_index, row_data in enumerate(rows):
            for column_index, value in enumerate(row_data):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                table.setItem(row_index, column_index, item)
        table.resizeRowsToContents()

    def getDefaultPowerItems(self):
        try:
            cfg = Tool.read_config("DefaultPower")
            raw_items = cfg.get("items", "")
            parsed_items = json.loads(raw_items) if raw_items else []
        except Exception:
            parsed_items = []

        if not isinstance(parsed_items, list):
            parsed_items = []

        default_items = []
        type_counts = {"GPW": 0, "PSW": 0, "GPP": 0}
        for item in parsed_items:
            if not isinstance(item, dict):
                continue

            power_type = str(item.get("type", "")).strip().upper()
            power_name = str(item.get("name", "")).strip()
            if power_type not in ("GPW", "PSW", "GPP") or not power_name:
                continue

            type_counts[power_type] += 1
            serial_key = str(item.get("serial_key", "")).strip()
            if not serial_key:
                if power_type == "GPW":
                    serial_key = f"power_supply_square{type_counts[power_type]}"
                elif power_type == "PSW":
                    serial_key = "power_supply_long"
                elif power_type == "GPP":
                    serial_key = "power_supply_gpp"

            default_items.append(
                {
                    "name": power_name,
                    "type": power_type,
                    "serial_key": serial_key,
                }
            )

        if default_items:
            return default_items
        return [dict(item) for item in DEFAULT_POWER_ITEMS]

    def loadDefaultPowerWidgets(self):
        self.default_power_items = self.getDefaultPowerItems()
        self.default_power_widgets = []
        self.default_power_widget_items = []

        for item in self.default_power_items:
            if self.power_name_exists(item["name"]):
                continue

            widget_obj = self.create_power_widget(item["type"], item["name"])
            widget_obj.serial_config_key = item.get("serial_key", "")
            widget_obj.is_default_power = True
            self.AddSubWin(widget_obj)
            self.default_power_widgets.append(widget_obj)
            self.default_power_widget_items.append((widget_obj, item))
            self.registerDefaultPowerWidget(widget_obj)

    def registerDefaultPowerWidget(self, widget_obj):
        if isinstance(widget_obj, SquarePower) and self.power_control_obj1 is None:
            self.power_control_obj1 = widget_obj
        elif isinstance(widget_obj, LongPower) and self.power_control_obj5 is None:
            self.power_control_obj5 = widget_obj
        elif isinstance(widget_obj, GPPPower) and self.power_control_obj_gpp is None:
            self.power_control_obj_gpp = widget_obj

    def getWidgetSerialKey(self, widget_obj):
        return str(getattr(widget_obj, "serial_config_key", "") or "").strip()

    def applyConfiguredPorts(self):
        cfg = Tool.read_config("Serial")

        for widget_obj, _ in self.default_power_widget_items:
            serial_key = self.getWidgetSerialKey(widget_obj)
            self.applyConfiguredPort(widget_obj, cfg.get(serial_key, ""))

        self.startup_square_widgets = [
            widget_obj
            for widget_obj in self.default_power_widgets
            if isinstance(widget_obj, SquarePower)
        ]
        self.startup_auto_connect = (cfg.get("auto_connect", "False") == "True")
        self.startup_auto_output = (cfg.get("auto_output", "False") == "True")

    def applyConfiguredPort(self, widget_obj, configured_port):
        if not hasattr(widget_obj, "portchoose"):
            return

        configured_port = str(configured_port or "").strip()
        if configured_port and Tool.check_incombox(widget_obj.portchoose, configured_port):
            widget_obj.portchoose.setCurrentText(configured_port)
            return

        if widget_obj.portchoose.count() > 0:
            widget_obj.portchoose.setCurrentIndex(0)
            return

        print(f"{widget_obj.name} 未找到可用连接资源")

    def applySafetyConfig(self):
        cfg = Tool.read_config("Safty")
        square_widgets = [
            widget_obj
            for widget_obj in self.default_power_widgets
            if isinstance(widget_obj, SquarePower)
        ]

        for index, widget_obj in enumerate(square_widgets, start=1):
            widget_obj.ch1_safty = float(cfg.get(f"current_limit{index}_ch1", "100"))
            widget_obj.ch2_safty = float(cfg.get(f"current_limit{index}_ch2", "100"))
            print(f"square safety ch1[{index}] = {widget_obj.ch1_safty}")
            print(f"square safety ch2[{index}] = {widget_obj.ch2_safty}")

        if self.power_control_obj5 is not None:
            self.power_control_obj5.safty = float(cfg.get("current_limit5_ch1", "100"))
            print(f"long safety = {self.power_control_obj5.safty}")

        if self.power_control_obj_gpp is not None:
            self.power_control_obj_gpp.ch1_safty = float(cfg.get("current_limit_gpp_ch1", "100"))
            self.power_control_obj_gpp.ch2_safty = float(cfg.get("current_limit_gpp_ch2", "100"))
            print(f"gpp safety ch1 = {self.power_control_obj_gpp.ch1_safty}")
            print(f"gpp safety ch2 = {self.power_control_obj_gpp.ch2_safty}")

    def getConfigPath(self):
        return os.path.join(root_path, "Auto_config.ini")

    def getPowerButtonStyle(self):
        return (
            "QPushButton {"
            "font: 12pt \"微软雅黑\";"
            "color: #1f2d3d;"
            "background-color: #eef3f8;"
            "border: 1px solid #b8c6d6;"
            "border-left: 6px solid #90a4b8;"
            "border-radius: 8px;"
            "padding: 10px 14px;"
            "text-align: left;"
            "min-height: 44px;"
            "}"
            "QPushButton:hover {"
            "background-color: #dfeaf7;"
            "border-color: #5f8fc7;"
            "}"
            "QPushButton:pressed {"
            "background-color: #0b5cab;"
            "color: #ffffff;"
            "border-color: #084785;"
            "}"
            "QPushButton:checked {"
            "font: 75 12pt \"微软雅黑\";"
            "color: #ffffff;"
            "background-color: #0f6bdc;"
            "border: 1px solid #084785;"
            "border-left: 10px solid #ffd34d;"
            "}"
        )

    def getComboPorts(self, combox):
        ports = []
        for i in range(combox.count()):
            port = combox.itemText(i).strip()
            if port and port not in ports:
                ports.append(port)
        return ports

    def refreshWidgetConnectionOptions(self, widget_obj):
        if hasattr(widget_obj, "refresh_connection_options"):
            try:
                return widget_obj.refresh_connection_options(show_message=False)
            except TypeError:
                return widget_obj.refresh_connection_options()

        if hasattr(widget_obj, "portchoose"):
            Tool.port_check(widget_obj.portchoose)
            return self.getComboPorts(widget_obj.portchoose)

        return []

    def getStartupCandidatePorts(self, widget_obj, config_port="", excluded_ports=None):
        ports = self.getComboPorts(widget_obj.portchoose)
        excluded_ports = excluded_ports or set()
        candidates = []

        for port in [str(config_port).strip(), widget_obj.portchoose.currentText().strip()]:
            if port and port in ports and port not in excluded_ports and port not in candidates:
                candidates.append(port)

        if len(ports) == 1:
            only_port = ports[0]
            if only_port not in excluded_ports and only_port not in candidates:
                candidates.append(only_port)

        return candidates

    def detectWidgetOnStartup(self, widget_obj, config_port="", keep_connected=False, excluded_ports=None):
        ports = self.getStartupCandidatePorts(widget_obj, config_port=config_port, excluded_ports=excluded_ports)
        original_port = widget_obj.portchoose.currentText().strip()

        for port in ports:
            widget_obj.portchoose.setCurrentText(port)
            result = widget_obj.startup_port_open()
            success = bool(result and result[0])
            if not success:
                continue

            if not keep_connected:
                widget_obj.power_port_close()
                widget_obj.portchoose.setCurrentText(port)
            return True, port

        available_ports = self.getComboPorts(widget_obj.portchoose)
        if original_port and Tool.check_incombox(widget_obj.portchoose, original_port):
            widget_obj.portchoose.setCurrentText(original_port)
        elif available_ports:
            widget_obj.portchoose.setCurrentText(available_ports[0])
        return False, None

    def getAutoConnectCandidatePorts(self, widget_obj, config_port="", excluded_ports=None):
        self.refreshWidgetConnectionOptions(widget_obj)
        ports = self.getComboPorts(widget_obj.portchoose)
        excluded_ports = excluded_ports or set()
        candidates = []

        preferred_ports = [
            str(config_port or "").strip(),
            widget_obj.portchoose.currentText().strip(),
        ]
        for port in preferred_ports:
            if port and port in ports and port not in excluded_ports and port not in candidates:
                candidates.append(port)

        for port in ports:
            if port not in excluded_ports and port not in candidates:
                candidates.append(port)

        return candidates

    def autoConnectWidget(self, widget_obj, config_port="", excluded_ports=None):
        excluded_ports = excluded_ports or set()
        serial_key = self.getWidgetSerialKey(widget_obj)
        original_port = widget_obj.portchoose.currentText().strip()

        if getattr(widget_obj, "isConnected", False):
            connected_port = widget_obj.portchoose.currentText().strip()
            if connected_port:
                if serial_key:
                    Tool.update_config_option("Serial", serial_key, connected_port)
                return True, connected_port, "已连接"

        candidates = self.getAutoConnectCandidatePorts(
            widget_obj,
            config_port=config_port,
            excluded_ports=excluded_ports,
        )

        for port in candidates:
            widget_obj.portchoose.setCurrentText(port)
            result = widget_obj.startup_port_open()
            if result and result[0]:
                if serial_key:
                    Tool.update_config_option("Serial", serial_key, port)
                return True, port, ""

            try:
                if getattr(widget_obj, "isConnected", False):
                    widget_obj.power_port_close()
            except Exception:
                pass

        available_ports = self.getComboPorts(widget_obj.portchoose)
        if original_port and Tool.check_incombox(widget_obj.portchoose, original_port):
            widget_obj.portchoose.setCurrentText(original_port)
        elif available_ports:
            widget_obj.portchoose.setCurrentIndex(0)
        return False, None, "未识别到匹配设备"

    def oneKeyConnect(self):
        if not self.default_power_widget_items:
            QtWidgets.QMessageBox.warning(self, "提示", "未配置默认电源")
            return

        self.setGlobalControlButtonsEnabled(False)
        try:
            serial_cfg = Tool.read_config("Serial")
            occupied_ports = set()
            success_items = []
            failed_items = []

            for widget_obj, item in self.default_power_widget_items:
                serial_key = self.getWidgetSerialKey(widget_obj)
                ok, port, message = self.autoConnectWidget(
                    widget_obj,
                    config_port=serial_cfg.get(serial_key, ""),
                    excluded_ports=occupied_ports,
                )
                if ok:
                    occupied_ports.add(port)
                    success_items.append(f"{widget_obj.name} -> {port}")
                else:
                    failed_items.append(f"{widget_obj.name}: {message}")

            message_lines = []
            if success_items:
                message_lines.append("连接成功：")
                message_lines.extend(success_items)
            if failed_items:
                if message_lines:
                    message_lines.append("")
                message_lines.append("连接失败：")
                message_lines.extend(failed_items)

            if not message_lines:
                message_lines.append("未执行连接操作")

            QtWidgets.QMessageBox.information(self, "一键连接完成", "\n".join(message_lines))
        finally:
            self.refreshTotalControlSummary()
            self.setGlobalControlButtonsEnabled(True)

    def setGlobalControlButtonsEnabled(self, enabled):
        for button in getattr(self, "global_control_buttons", []):
            button.setEnabled(enabled)

    def setBatchActionBusyText(self, action_name):
        original_text = []
        for button in getattr(self, "global_control_buttons", []):
            original_text.append((button, button.text()))
            if button.text() == action_name:
                button.setText(f"{action_name}执行中...")
        return original_text

    def restoreGlobalControlButtonText(self, original_text):
        for button, text in original_text:
            button.setText(text)

    def iterAllPowerWidgets(self):
        widgets = []
        for widget_obj in self.default_power_widgets + list(self.added_power_widgets.values()):
            if widget_obj not in widgets:
                widgets.append(widget_obj)
        return widgets

    def runBatchPowerAction(self, action_name, action_func_name):
        widgets = self.iterAllPowerWidgets()
        if not widgets:
            QtWidgets.QMessageBox.warning(self, "提示", "当前没有电源设备")
            return

        self.setGlobalControlButtonsEnabled(False)
        original_button_text = self.setBatchActionBusyText(action_name)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            success_items = []
            failed_items = []
            skipped_items = []

            for widget_obj in widgets:
                self.statusBar().showMessage(f"{action_name}：正在处理 {widget_obj.name}")
                QtWidgets.QApplication.processEvents()

                if not getattr(widget_obj, "isConnected", False):
                    skipped_items.append(f"{widget_obj.name}: 未连接")
                    QtWidgets.QApplication.processEvents()
                    continue

                action_func = getattr(widget_obj, action_func_name, None)
                if action_func is None:
                    failed_items.append(f"{widget_obj.name}: 不支持{action_name}")
                    QtWidgets.QApplication.processEvents()
                    continue

                try:
                    result = action_func()
                    if result is None or result[0]:
                        success_items.append(widget_obj.name)
                    else:
                        failed_items.append(
                            f"{widget_obj.name}: {result[1] if len(result) > 1 else action_name + '失败'}"
                        )
                except Exception as e:
                    failed_items.append(f"{widget_obj.name}: {e}")
                finally:
                    QtWidgets.QApplication.processEvents()

            message_lines = []
            if success_items:
                message_lines.append(f"{action_name}成功：")
                message_lines.extend(success_items)
            if skipped_items:
                if message_lines:
                    message_lines.append("")
                message_lines.append("跳过：")
                message_lines.extend(skipped_items)
            if failed_items:
                if message_lines:
                    message_lines.append("")
                message_lines.append(f"{action_name}失败：")
                message_lines.extend(failed_items)

            QtWidgets.QMessageBox.information(self, action_name, "\n".join(message_lines))
        finally:
            self.statusBar().clearMessage()
            self.restoreGlobalControlButtonText(original_button_text)
            QtWidgets.QApplication.restoreOverrideCursor()
            self.refreshTotalControlSummary()
            self.setGlobalControlButtonsEnabled(True)
            QtWidgets.QApplication.processEvents()

    def oneKeyPowerOn(self):
        self.runBatchPowerAction("一键上电", "output_open_tcp")

    def oneKeyPowerOff(self):
        self.runBatchPowerAction("一键下电", "output_close_tcp")

    def detectStartupPowers(self, square_widgets=None, keep_connected=False):
        serial_cfg = Tool.read_config("Serial")
        occupied_ports = set()
        square_detected = False
        long_detected = False
        gpp_detected = False
        selected_button_name = ""

        for widget_obj, item in self.default_power_widget_items:
            serial_key = self.getWidgetSerialKey(widget_obj)
            detected, port = self.detectWidgetOnStartup(
                widget_obj,
                config_port=serial_cfg.get(serial_key, ""),
                keep_connected=keep_connected,
                excluded_ports=occupied_ports,
            )
            if not detected:
                continue

            occupied_ports.add(port)
            if serial_key:
                Tool.update_config_option("Serial", serial_key, port)
            if not selected_button_name:
                selected_button_name = "Btn" + widget_obj.name

            if isinstance(widget_obj, SquarePower):
                square_detected = True
            elif isinstance(widget_obj, LongPower):
                long_detected = True
            elif isinstance(widget_obj, GPPPower):
                gpp_detected = True

            QtWidgets.QMessageBox.information(self, "提示", f"已检测到{widget_obj.name}：{port}")

        if not selected_button_name and self.power_control_obj5 is not None:
            selected_button_name = "Btn" + self.power_control_obj5.name

        if not square_detected and not long_detected and not gpp_detected:
            QtWidgets.QMessageBox.information(self, "提示", "未检测到电源设备")

        return selected_button_name, square_detected, long_detected, gpp_detected

    def runStartupDetection(self):
        self.initial_button_name, square_detected, long_detected, gpp_detected = self.detectStartupPowers(
            self.startup_square_widgets,
            keep_connected=self.startup_auto_connect
        )

        if self.startup_auto_output and not self.startup_auto_output_done:
            for widget_obj in self.default_power_widgets:
                if widget_obj.isConnected:
                    output_open = getattr(widget_obj, "output_open_tcp", None)
                    if output_open is not None:
                        output_open()
            self.startup_auto_output_done = True

        if square_detected and self.initial_button_name and self.initial_button_name in self.leftBtnDict:
            self.leftBtnCallback(self.initial_button_name)
        elif (
            gpp_detected
            and self.power_control_obj_gpp is not None
            and ("Btn" + self.power_control_obj_gpp.name) in self.leftBtnDict
        ):
            self.leftBtnCallback("Btn" + self.power_control_obj_gpp.name)
        elif self.power_control_obj5 is not None and ("Btn" + self.power_control_obj5.name) in self.leftBtnDict:
            self.leftBtnCallback("Btn" + self.power_control_obj5.name)

    def loadPersistedAddedPowers(self):
        config = configparser.ConfigParser()
        config.read(self.getConfigPath(), encoding="utf-8")

        raw_items = "[]"
        if config.has_section("CustomPower"):
            raw_items = config.get("CustomPower", "items", fallback="[]")

        try:
            power_items = json.loads(raw_items)
        except Exception:
            power_items = []

        for item in power_items:
            if not isinstance(item, dict):
                continue

            power_type = item.get("type")
            power_name = str(item.get("name", "")).strip()
            if power_type not in ["GPW", "PSW", "GPP", "MU_N"] or not power_name:
                continue
            if self.power_name_exists(power_name):
                continue

            widget_obj = self.create_power_widget(
                power_type,
                power_name,
                channel_count=item.get("channels"),
            )
            self.AddSubWin(widget_obj)
            self.added_power_widgets[power_name] = widget_obj

    def savePersistedAddedPowers(self):
        config = configparser.ConfigParser()
        config.read(self.getConfigPath(), encoding="utf-8")

        if not config.has_section("CustomPower"):
            config.add_section("CustomPower")

        power_items = []
        for widget_obj in self.added_power_widgets.values():
            item = {"name": widget_obj.name}
            if isinstance(widget_obj, LongPower):
                item["type"] = "PSW"
            elif isinstance(widget_obj, GPPPower):
                item["type"] = "GPP"
            elif isinstance(widget_obj, MUNPower):
                item["type"] = "MU_N"
                item["channels"] = widget_obj.channel_count
            else:
                item["type"] = "GPW"
            power_items.append(item)

        for section_name in list(config.sections()):
            if section_name.startswith("MU_N_LIMITS:"):
                config.remove_section(section_name)

        config.set("CustomPower", "items", json.dumps(power_items, ensure_ascii=False))
        for widget_obj in self.added_power_widgets.values():
            if not isinstance(widget_obj, MUNPower):
                continue
            section_name = f"MU_N_LIMITS:{widget_obj.name}"
            if not config.has_section(section_name):
                config.add_section(section_name)
            for option, value in widget_obj.export_limit_settings().items():
                config.set(section_name, option, value)
        with open(self.getConfigPath(), "w", encoding="utf-8") as f:
            config.write(f)

    def adjustStartupWindow(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        width_margin = 24
        height_margin = 24
        target_width = min(self.width(), max(available.width() - width_margin, 0))
        target_height = min(self.height(), max(available.height() - height_margin, 0))

        if target_width > 0 and target_height > 0:
            self.resize(target_width, target_height)

        x = available.x() + max((available.width() - self.width()) // 2, 0)
        y = available.y() + max((available.height() - self.height()) // 2, 0)
        self.move(x, y)

    def showAbout(self):
        # 读取 CSV 文件
        df = pd.read_csv("更新内容.csv", header=None, names=["version", "notes"])
        # 将 DataFrame 转换为 HTML 表格字符串
        html_table = df.to_html(index=False, border=1)
        # 创建关于窗口
        aboutWin = QtWidgets.QDialog(self)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(400, 300)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")
        # 创建 QTextEdit 控件
        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(html_table)  # 设置 HTML 内容
        # 使用布局管理器
        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)  # 将 QTextEdit 添加到布局中
        # 设置布局边距
        layout.setContentsMargins(10, 10, 10, 10)
        # 显示窗口
        aboutWin.show()

    def showVersionAbout(self):
        aboutWin = QtWidgets.QDialog(self)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(520, 360)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")

        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(get_about_html())

        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)
        layout.setContentsMargins(10, 10, 10, 10)
        aboutWin.show()

    def openVersionAboutDialog(self):
        if self.version_about_dialog is not None:
            self.version_about_dialog.show()
            self.version_about_dialog.raise_()
            self.version_about_dialog.activateWindow()
            return

        aboutWin = QtWidgets.QDialog(self)
        self.version_about_dialog = aboutWin
        aboutWin.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        aboutWin.destroyed.connect(self._clearVersionAboutDialog)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(400, 300)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")

        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(get_about_html())

        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)
        layout.setContentsMargins(10, 10, 10, 10)
        aboutWin.show()

    def _clearVersionAboutDialog(self, *args):
        self.version_about_dialog = None

    def checkUpdateOnStartup(self):
        try:
            cfg = Tool.read_config("Update")
        except Exception as e:
            print(f"读取更新配置失败: {e}")
            return

        if cfg.get("enabled", "False") != "True":
            return
        if cfg.get("check_on_startup", "True") != "True":
            return

        manifest_url = cfg.get("manifest_url", "").strip()
        if not manifest_url:
            print("manifest_url is empty, skip update check")
            return

        if self.update_check_thread is not None and self.update_check_thread.isRunning():
            return

        try:
            timeout = int(cfg.get("request_timeout", "3"))
        except Exception:
            timeout = 3

        self.update_check_thread = UpdateCheckThread(VERSION, manifest_url, timeout, self)
        self.update_check_thread.update_checked.connect(self._handleUpdateCheckResult)
        self.update_check_thread.finished.connect(self._clearUpdateCheckThread)
        self.update_check_thread.start()

    def _openUpdateDownload(self, download_url):
        if download_url.startswith("http://") or download_url.startswith("https://") or download_url.startswith("file://"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(download_url))
            return

        local_path = os.path.abspath(download_url)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(local_path))

    def _clearUpdateCheckThread(self):
        self.update_check_thread = None

    def _handleUpdateCheckResult(self, result):
        if not result.success:
            print(f"更新检测失败: {result.error_message}")
            return

        if not result.has_update:
            print(f"当前已是最新版本: {VERSION}")
            return

        message = f"检测到新版本：{result.latest_version}\n当前版本：{VERSION}"
        if result.release_notes:
            message += f"\n\n更新内容：\n{result.release_notes}"

        if result.download_url:
            buttons = QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel
            reply = QtWidgets.QMessageBox.question(
                self,
                "发现新版本",
                message + "\n\n点击“确定”后将自动下载、替换并重启程序。",
                buttons,
                QtWidgets.QMessageBox.Ok
            )
            if reply == QtWidgets.QMessageBox.Ok:
                self._startAutoUpdate(result.download_url)
            return

        QtWidgets.QMessageBox.information(self, "发现新版本", message)

    def _startAutoUpdate(self, download_url):
        try:
            launch_update_installer(download_url)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "更新失败", f"启动自动更新失败：{e}")
            return

        self.is_updating = True
        QtWidgets.QMessageBox.information(self, "开始更新", "已开始自动更新，程序将关闭并在更新完成后自动重启。")
        self.close()

    def stopTcpServer(self):
        if self.tcp_server is None:
            return

        try:
            if self.tcp_server.isRunning():
                self.tcp_server.stop()
                self.tcp_server.wait(1000)
        except Exception as e:
            print(f"停止 TCP 服务异常: {e}")
        finally:
            self.tcp_server = None

    def update_data(self, filename):
        # 上传电源记录
        if not hasattr(self, "ftp"):
            print("FTP 未初始化，跳过上传")
            return

        json_data = json.load(open((os.path.expanduser("~")+"\\AppData\\Local\\YabCom\\common\\config\\terminal_recent_projects.json"), 'r', encoding='utf-8'))
        print(json_data)
        number = json_data[0]["Numbers"]
        ftp_dir = (
            f"/组网星01测试数据/02 每日历史数据/"
            f"正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据"
        )
        if not self.ftp.check_ftp_directory_exists(ftp_dir):
            self.ftp.make_dir(ftp_dir)
        self.ftp.moveto_dir(ftp_dir)
        self.ftp.upload_file(filename)

    def CurrentWarning(self, str1, str2, str3):
        self.alarm_player.play_warning()
        QtWidgets.QMessageBox.warning(self, f"{str1}警告", f"电流过高，请检查电源电流是否过高，当前{str2}电流为{str3}A")

    def VoltageWarning(self, str1, str2, str3):
        self.alarm_player.play_warning()
        QtWidgets.QMessageBox.warning(self, f"{str1}告警", f"电压过高，请检查电源电压是否过高，当前{str2}电压为{str3}V")

    def start_info(self, name, v, i):
        reply = QtWidgets.QMessageBox.question(self,
                                               f'{name}',
                                               f"当前设置电压{v}V，电流{i}A，是否正确？",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.power_control_obj5.pressNo = False
        else:
            self.power_control_obj5.pressNo = True


    def addBTN(self):
        AddBtnCustom = QtWidgets.QPushButton(self.frame_left)
        AddBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        AddBtnCustom.setObjectName("addBtn")
        n=self.leftlayout.count()
        self.leftlayout.addWidget(AddBtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)
        AddBtnCustom.setText("添加电源")
        AddBtnCustom.clicked.connect(self.openAddPowerDialog)

    def delBTN(self):
        DelBtnCustom = QtWidgets.QPushButton(self.frame_left)
        DelBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        DelBtnCustom.setObjectName("delBtn")
        n=self.leftlayout.count()
        self.leftlayout.addWidget(DelBtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)
        DelBtnCustom.setText("删除电源")
        DelBtnCustom.clicked.connect(self.openDeletePowerDialog)

    def openAddPowerDialog(self):
        add_dialog = AddPowerDialog(self)
        if add_dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        power_type = add_dialog.get_power_type()
        power_name = add_dialog.get_power_name()
        channel_count = add_dialog.get_channel_count() if power_type == "MU_N" else None

        if self.power_name_exists(power_name):
            QtWidgets.QMessageBox.warning(self, "提示", f"电源名称“{power_name}”已存在，请重新命名")
            return

        widget_obj = self.create_power_widget(power_type, power_name, channel_count=channel_count)
        self.AddSubWin(widget_obj)
        self.added_power_widgets[power_name] = widget_obj
        self.savePersistedAddedPowers()
        self.leftBtnCallback("Btn" + widget_obj.name)

    def power_name_exists(self, power_name):
        return ("Btn" + power_name) in self.leftBtnDict

    def create_power_widget(self, power_type, power_name, channel_count=None):
        if power_type == "PSW":
            widget_obj = LongPower(power_name)
            widget_obj.current_warn.connect(self.CurrentWarning)
            widget_obj.start_signal.connect(self.start_info)
            widget_obj.dataUpSignal.connect(self.update_data)
            return widget_obj
        if power_type == "GPP":
            widget_obj = GPPPower(power_name)
            widget_obj.current_warn.connect(self.CurrentWarning)
            return widget_obj
        if power_type == "MU_N":
            widget_obj = MUNPower(
                power_name,
                channel_count=channel_count or 3,
            )
            widget_obj.current_warn.connect(self.CurrentWarning)
            widget_obj.voltage_warn.connect(self.VoltageWarning)
            widget_obj.structure_changed.connect(self.savePersistedAddedPowers)
            return widget_obj

        widget_obj = SquarePower(power_name)
        widget_obj.current_warn.connect(self.CurrentWarning)
        return widget_obj

    def removeLastAddedPower(self):
        if not self.added_power_widgets:
            QtWidgets.QMessageBox.information(self, "提示", "当前没有可删除的新增电源")
            return
        last_name = next(reversed(self.added_power_widgets))
        self.DelSubWin(self.added_power_widgets[last_name])

    def openDeletePowerDialog(self):
        if not self.added_power_widgets:
            QtWidgets.QMessageBox.information(self, "提示", "当前没有可删除的新增电源")
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("删除电源")
        dialog.setModal(True)
        dialog.resize(300, 130)

        layout = QtWidgets.QVBoxLayout(dialog)
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        combo = QtWidgets.QComboBox(dialog)
        for name in self.added_power_widgets:
            combo.addItem(name)
        form.addRow("选择要删除的电源：", combo)
        layout.addLayout(form)

        button_box = QtWidgets.QDialogButtonBox(dialog)
        confirm_btn = button_box.addButton("删除", QtWidgets.QDialogButtonBox.AcceptRole)
        confirm_btn.setStyleSheet("color: #c0392b;")
        button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        selected_name = combo.currentText()
        if selected_name not in self.added_power_widgets:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f'确定要删除电源"{selected_name}"吗？',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.DelSubWin(self.added_power_widgets[selected_name])

    def showPowerContextMenu(self, widgetObj, button, pos):
        menu = QtWidgets.QMenu(button)
        delete_action = menu.addAction("删除电源")
        operation_logger = QtWidgets.QApplication.instance().property("operation_logger")
        if operation_logger is not None:
            operation_logger.track_action(delete_action)

        if widgetObj not in self.added_power_widgets.values():
            delete_action.setEnabled(False)
        else:
            delete_action.triggered.connect(lambda: self.DelSubWin(widgetObj))

        menu.exec_(button.mapToGlobal(pos))

    def AddSubWin(self,widgetObj, show_controls=True):
        # 增加左侧按钮
        # self.leftlayout=QGridLayout()
        BtnCustom = QtWidgets.QPushButton(self.frame_left)
        BtnCustom.setStyleSheet(self.getPowerButtonStyle())
        BtnCustom.setCheckable(True)
        BtnCustom.setObjectName("Btn"+widgetObj.name)
        n=self.leftlayout.count()
        self.leftlayout.addWidget(BtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)  # 这个必须动态加入才能自动布局

        BtnCustom.setText(widgetObj.name)  # 自定义页面名称
        BtnCustom.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        BtnCustom.customContextMenuRequested.connect(
            lambda pos, obj=widgetObj, btn=BtnCustom: self.showPowerContextMenu(obj, btn, pos)
        )

        # 增加右侧 stackedWidget 的页面
        page_custom = QtWidgets.QWidget()
        page_custom.setObjectName("Page"+widgetObj.name)
        self.gridLayout_custom = QtWidgets.QGridLayout(page_custom)
        self.gridLayout_custom.setObjectName("gridLayout_custom")
        self.gridLayout_custom.setContentsMargins(1, 1, 1, 1)

        if show_controls:
            widgetObj.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            if isinstance(widgetObj, (SquarePower, LongPower)):
                self.gridLayout_custom.setContentsMargins(0, 0, 0, 0)
                self.gridLayout_custom.addWidget(widgetObj, 0, 0, 1, 1)
            else:
                scroll_area = QtWidgets.QScrollArea(page_custom)
                scroll_area.setObjectName("Scroll"+widgetObj.name)
                scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
                scroll_area.setWidgetResizable(True)
                scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
                scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
                scroll_area.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                if isinstance(widgetObj, MUNPower):
                    widgetObj.setMinimumHeight(0)
                else:
                    widgetObj.adjustSize()
                    widgetObj.setMinimumSize(widgetObj.sizeHint())
                scroll_area.setWidget(widgetObj)
                self.gridLayout_custom.addWidget(scroll_area, 1, 1, 1, 1)

        self.stackedWidget.addWidget(page_custom)  # 添加到右侧 stackedWidget

        self.bindBtnWidget[BtnCustom.objectName()] = page_custom.objectName()
        self.leftBtnDict [BtnCustom.objectName()] = BtnCustom
        self.rightPageDict[BtnCustom.objectName() ]=page_custom

        # 绑定页面与按钮
        BtnCustom.clicked.connect( lambda: self.leftBtnCallback(BtnCustom.objectName()) )

    def DelSubWin(self,widgetObj):
        # 删除左侧按钮
        BtnCustom=self.leftBtnDict["Btn"+widgetObj.name]
        self.leftlayout.removeWidget(BtnCustom)
        BtnCustom.deleteLater()
        BtnCustom.setParent(None)

        # 删除右侧 stackedWidget 的页面
        page_custom=self.rightPageDict["Btn"+widgetObj.name]
        self.stackedWidget.removeWidget(page_custom)
        page_custom.deleteLater()
        page_custom.setParent(None)

        # 删除按钮与页面的绑定
        del self.leftBtnDict["Btn"+widgetObj.name]
        del self.rightPageDict["Btn"+widgetObj.name]
        del self.bindBtnWidget[BtnCustom.objectName()]

        # 删除页面对应对象
        if widgetObj:
            if widgetObj in self.added_power_widgets.values():
                self.added_power_widgets.pop(widgetObj.name, None)
            if isinstance(widgetObj, SquarePower) and widgetObj in SquarePower.get_instances():
                SquarePower.get_instances().remove(widgetObj)
            if isinstance(widgetObj, LongPower) and widgetObj in LongPower.get_instances():
                LongPower.get_instances().remove(widgetObj)
            if isinstance(widgetObj, GPPPower) and widgetObj in GPPPower.get_instances():
                GPPPower.get_instances().remove(widgetObj)
            if isinstance(widgetObj, MUNPower) and widgetObj in MUNPower.get_instances():
                MUNPower.get_instances().remove(widgetObj)
            self.savePersistedAddedPowers()

        if self.leftBtnDict:
            self.leftBtnCallback(next(iter(self.leftBtnDict)))

    def leftBtnCallback(self,BtnobjectName):

        for k, v in self.leftBtnDict.items():
            if k==BtnobjectName:
                if k == "Btn总控":
                    self.refreshTotalControlSummary()
                self.stackedWidget.setCurrentWidget(self.rightPageDict[k] )
                self.leftBtnDict[k].setChecked(True)

            else:
                self.leftBtnDict[k].setChecked(False)

    def CreateDbEngine(self):
        # TODO: 创建数据库引擎，并创建访问锁
        pass

    def closeEvent(self, event):
        if self.is_updating:
            self.stopTcpServer()
            event.accept()
            os._exit(0)
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "退出确认",
            "是否退出程序？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.stopTcpServer()
            event.accept()
            os._exit(0)
        else:
            event.ignore()

