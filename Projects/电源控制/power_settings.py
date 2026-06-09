# -*- coding: utf-8 -*-
"""电源场景预设与设置窗口"""

import copy
import json

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QRadioButton,
    QButtonGroup, QStackedWidget, QWidget, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QCheckBox, QMessageBox,
    QHeaderView,
)

from .tool import Tool

SCENARIO_META = [
    ("gxt_only", "光学头单机", "1个长条电源 42V/3.5A，仅连接光学头"),
    ("gxt_fgw", "光学头+FGW光放", "2长条+2方形，连接光学头与FGW光放（电压电流可在此调整）"),
    ("gxt_xw", "光学头+XW光放", "2长条：光学头 42V/3.5A + XW光放 5.4V/10A"),
    ("manual", "手动配置", "自定义电源数量、类型与预设参数"),
]


def _base_serial():
    return {"auto_connect": False, "auto_output": False}


def _section_label(text):
    label = QLabel(text)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    label.setFont(font)
    return label


def get_scenario_config(scenario_id):
    """返回各预设场景的默认 power_config 结构（不含 scenario 字段）"""
    serial = _base_serial()
    if scenario_id == "gxt_only":
        return {
            "serial": copy.deepcopy(serial),
            "devices": [
                {
                    "id": "GXT",
                    "name": "光学头电源",
                    "type": "long",
                    "port": "COM",
                    "default_voltage": 42,
                    "default_current": 3.5,
                    "current_limit": 3.5,
                    "remote": True,
                }
            ],
        }
    if scenario_id == "gxt_fgw":
        return {
            "serial": copy.deepcopy(serial),
            "devices": [
                {
                    "id": "GXT",
                    "name": "光学头电源",
                    "type": "long",
                    "port": "COM",
                    "default_voltage": 42,
                    "default_current": 3.5,
                    "current_limit": 3.5,
                    "remote": True,
                },
                {
                    "id": "GF",
                    "name": "FGW光放电源",
                    "type": "long",
                    "port": "COM",
                    "default_voltage": 5,
                    "default_current": 2,
                    "current_limit": 2,
                    "remote": True,
                },
                {
                    "id": "SQ1",
                    "name": "方形电源1",
                    "type": "square",
                    "port": "COM",
                    "ch1": {"voltage": 5, "current": 1},
                    "ch2": {"voltage": 12, "current": 0.5},
                    "current_limit_ch1": 100,
                    "current_limit_ch2": 100,
                    "remote": False,
                },
                {
                    "id": "SQ2",
                    "name": "方形电源2",
                    "type": "square",
                    "port": "COM",
                    "ch1": {"voltage": 5, "current": 1},
                    "ch2": {"voltage": 12, "current": 0.5},
                    "current_limit_ch1": 100,
                    "current_limit_ch2": 100,
                    "remote": False,
                },
            ],
        }
    if scenario_id == "gxt_xw":
        return {
            "serial": copy.deepcopy(serial),
            "devices": [
                {
                    "id": "GXT",
                    "name": "光学头电源",
                    "type": "long",
                    "port": "COM",
                    "default_voltage": 42,
                    "default_current": 3.5,
                    "current_limit": 3.5,
                    "remote": True,
                },
                {
                    "id": "GF",
                    "name": "XW光放电源",
                    "type": "long",
                    "port": "COM",
                    "default_voltage": 5.4,
                    "default_current": 10,
                    "current_limit": 10,
                    "remote": True,
                },
            ],
        }
    return Tool.read_power_config_raw()


class PresetDeviceTable(QWidget):
    """预设场景下的设备参数表（可编辑串口与电压电流）"""

    COL_ID, COL_NAME, COL_TYPE, COL_PORT = 0, 1, 2, 3
    COL_V, COL_I, COL_CH2V, COL_CH2I, COL_REMOTE = 4, 5, 6, 7, 8

    HEADERS = [
        "ID", "名称", "类型", "串口", "电压/CH1压", "电流/CH1流",
        "CH2压", "CH2流", "远程",
    ]

    def __init__(self, parent=None, manual_mode=False):
        super().__init__(parent)
        self.manual_mode = manual_mode
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def load_devices(self, devices):
        self.table.setRowCount(0)
        for dev in devices:
            self._append_row(dev)

    def _append_row(self, dev):
        row = self.table.rowCount()
        self.table.insertRow(row)
        power_type = dev.get("type", "long")
        ch1 = dev.get("ch1", {})
        ch2 = dev.get("ch2", {})
        v = dev.get("default_voltage", ch1.get("voltage", 0))
        i = dev.get("default_current", ch1.get("current", 0))
        items = [
            dev.get("id", ""),
            dev.get("name", ""),
            power_type,
            dev.get("port", "COM"),
            str(v),
            str(i),
            str(ch2.get("voltage", "")),
            str(ch2.get("current", "")),
            "是" if dev.get("remote", power_type == "long") else "否",
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if not self.manual_mode and col in (self.COL_ID, self.COL_TYPE):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, col, item)

    def export_devices(self):
        devices = []
        for row in range(self.table.rowCount()):
            power_type = self._cell(row, self.COL_TYPE)
            dev = {
                "id": self._cell(row, self.COL_ID),
                "name": self._cell(row, self.COL_NAME),
                "type": power_type,
                "port": self._cell(row, self.COL_PORT) or "COM",
                "remote": self._cell(row, self.COL_REMOTE) == "是",
            }
            if power_type == "long":
                dev["default_voltage"] = float(self._cell(row, self.COL_V) or 0)
                dev["default_current"] = float(self._cell(row, self.COL_I) or 0)
                dev["current_limit"] = dev["default_current"]
            else:
                dev["ch1"] = {
                    "voltage": float(self._cell(row, self.COL_V) or 0),
                    "current": float(self._cell(row, self.COL_I) or 0),
                }
                dev["ch2"] = {
                    "voltage": float(self._cell(row, self.COL_CH2V) or 0),
                    "current": float(self._cell(row, self.COL_CH2I) or 0),
                }
                dev["current_limit_ch1"] = dev["ch1"]["current"]
                dev["current_limit_ch2"] = dev["ch2"]["current"]
            devices.append(dev)
        return devices

    def _cell(self, row, col):
        item = self.table.item(row, col)
        return item.text().strip() if item else ""


class ManualDeviceEditor(QWidget):
    """手动配置：增删设备行"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        hint = QLabel("手动添加或删除电源，填写各设备参数后保存。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = PresetDeviceTable(manual_mode=True)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add_long = QPushButton("添加长条电源")
        self.btn_add_square = QPushButton("添加方形电源")
        self.btn_remove = QPushButton("删除选中")
        self.btn_add_long.clicked.connect(self._add_long)
        self.btn_add_square.clicked.connect(self._add_square)
        self.btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.btn_add_long)
        btn_row.addWidget(self.btn_add_square)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def load_devices(self, devices):
        self.table.load_devices(devices)

    def export_devices(self):
        return self.table.export_devices()

    def _add_long(self):
        n = self.table.table.rowCount() + 1
        self.table._append_row({
            "id": f"LONG{n}",
            "name": f"长条电源{n}",
            "type": "long",
            "port": "COM",
            "default_voltage": 42,
            "default_current": 3.5,
            "remote": True,
        })

    def _add_square(self):
        n = self.table.table.rowCount() + 1
        self.table._append_row({
            "id": f"SQ{n}",
            "name": f"方形电源{n}",
            "type": "square",
            "port": "COM",
            "ch1": {"voltage": 5, "current": 1},
            "ch2": {"voltage": 12, "current": 0.5},
            "remote": False,
        })

    def _remove_selected(self):
        rows = sorted({i.row() for i in self.table.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的行")
            return
        for row in rows:
            self.table.table.removeRow(row)


class PowerSettingsDialog(QDialog):
    """电源场景与手动配置设置窗口"""

    def __init__(self, parent=None, require_apply=False):
        super().__init__(parent)
        self.require_apply = require_apply
        self.setWindowTitle("电源场景设置")
        self.setMinimumSize(860, 560)
        self.resize(860, 560)
        self.setObjectName("powerSettingsDialog")
        # 使用系统默认灰色窗口底色，不继承主界面自定义背景色
        self.setStyleSheet(
            "#powerSettingsDialog, #powerSettingsDialog QWidget {"
            "background-color: palette(window);"
            "color: palette(windowText);"
            "}"
        )

        self._current_raw = Tool.read_power_config_raw()
        self._scenario_pages = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(_section_label("选择使用场景"))
        scene_panel = QWidget()
        scene_layout = QVBoxLayout(scene_panel)
        scene_layout.setContentsMargins(8, 0, 8, 0)
        scene_layout.setSpacing(8)
        self.scene_group = QButtonGroup(self)
        for idx, (sid, title, desc) in enumerate(SCENARIO_META):
            rb = QRadioButton(f"{title}\n{desc}")
            rb.setProperty("scenario_id", sid)
            rb.setMinimumHeight(44)
            self.scene_group.addButton(rb, idx)
            scene_layout.addWidget(rb)
        root.addWidget(scene_panel)

        root.addWidget(_section_label("串口行为"))
        serial_panel = QWidget()
        serial_layout = QVBoxLayout(serial_panel)
        serial_layout.setContentsMargins(8, 0, 8, 0)
        serial_layout.setSpacing(6)
        self.chk_auto_connect = QCheckBox("启动时自动连接串口")
        self.chk_auto_output = QCheckBox("启动时自动开启输出")
        serial_layout.addWidget(self.chk_auto_connect)
        serial_layout.addWidget(self.chk_auto_output)
        root.addWidget(serial_panel)

        self.stack = QStackedWidget()
        for sid, title, _ in SCENARIO_META:
            if sid == "manual":
                page = ManualDeviceEditor()
            else:
                page = PresetDeviceTable()
            self._scenario_pages[sid] = page
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            param_label = QLabel(f"{title} — 设备参数（可修改串口与电压电流）")
            param_label.setWordWrap(True)
            wrap_layout.addWidget(param_label)
            wrap_layout.addWidget(page)
            self.stack.addWidget(wrap)
        root.addWidget(self.stack, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_apply = QPushButton("保存并应用")
        self.btn_cancel = QPushButton("取消")
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_cancel)
        root.addLayout(btn_row)

        self.scene_group.buttonClicked.connect(self._on_scenario_changed)
        self._load_from_config(self._current_raw)

        if self.require_apply:
            self.btn_cancel.setVisible(False)

    def _load_from_config(self, cfg):
        scenario = cfg.get("scenario", "gxt_only")
        serial = cfg.get("serial", {})
        self.chk_auto_connect.setChecked(bool(serial.get("auto_connect", False)))
        self.chk_auto_output.setChecked(bool(serial.get("auto_output", False)))

        for btn in self.scene_group.buttons():
            if btn.property("scenario_id") == scenario:
                btn.setChecked(True)
                break
        else:
            self.scene_group.button(0).setChecked(True)
            scenario = "gxt_only"

        self._on_scenario_changed(load_from_cfg=True)

    def _selected_scenario(self):
        btn = self.scene_group.checkedButton()
        return btn.property("scenario_id") if btn else "gxt_only"

    def _on_scenario_changed(self, _btn=None, load_from_cfg=False):
        sid = self._selected_scenario()
        idx = next(i for i, (s, _, _) in enumerate(SCENARIO_META) if s == sid)
        self.stack.setCurrentIndex(idx)
        saved_scenario = self._current_raw.get("scenario")
        saved_devices = self._current_raw.get("devices", [])
        if load_from_cfg and sid == saved_scenario:
            self._scenario_pages[sid].load_devices(saved_devices)
        elif sid == "manual":
            self._scenario_pages["manual"].load_devices(saved_devices if saved_scenario == "manual" else [])
        else:
            self._scenario_pages[sid].load_devices(get_scenario_config(sid)["devices"])

    def _on_apply(self):
        sid = self._selected_scenario()
        try:
            if sid == "manual":
                devices = self._scenario_pages["manual"].export_devices()
                if not devices:
                    raise ValueError("手动配置至少需要一个电源设备")
            else:
                devices = self._scenario_pages[sid].export_devices()
            ids = [d["id"] for d in devices]
            if any(not i for i in ids):
                raise ValueError("设备 ID 不能为空")
            if len(ids) != len(set(ids)):
                raise ValueError("设备 ID 不能重复")
            for d in devices:
                if d["type"] not in ("long", "square"):
                    raise ValueError(f"未知电源类型: {d['type']}")

            cfg = {
                "scenario": sid,
                "serial": {
                    "auto_connect": self.chk_auto_connect.isChecked(),
                    "auto_output": self.chk_auto_output.isChecked(),
                },
                "devices": devices,
            }
            Tool.save_power_config(cfg)
        except (ValueError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "配置错误", str(e))
            return
        except Exception as e:
            QMessageBox.warning(self, "配置错误", f"保存失败：{e}")
            return
        self.accept()

    @staticmethod
    def run_if_needed(parent=None):
        """首次未选择场景时弹出设置窗口"""
        if Tool.need_power_scenario_setup():
            dlg = PowerSettingsDialog(parent, require_apply=True)
            return dlg.exec_() == QDialog.Accepted
        return True
