# -*- coding: utf-8 -*-

import datetime
import json
import os
import threading

from PyQt5 import QtCore, QtWidgets, sip


class OperationLogger(QtCore.QObject):
    def __init__(self, app, log_dir=None):
        super(OperationLogger, self).__init__(app)
        self.app = app
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.log_dir = log_dir or os.path.join(project_root, "操作日志")
        self._write_lock = threading.Lock()
        os.makedirs(self.log_dir, exist_ok=True)

    def install_action_logging(self, root):
        if root is None:
            return

        if isinstance(root, QtWidgets.QAction):
            self.track_action(root)

        for action in root.findChildren(QtWidgets.QAction):
            self.track_action(action)

    def install_widget_logging(self, root):
        if root is None:
            return

        self._auto_track_object(root)

        for button in root.findChildren(QtWidgets.QAbstractButton):
            self.track_button(button)

        for line_edit in root.findChildren(QtWidgets.QLineEdit):
            self.track_line_edit(line_edit)

        for combo_box in root.findChildren(QtWidgets.QComboBox):
            self.track_combo_box(combo_box)

        for check_box in root.findChildren(QtWidgets.QCheckBox):
            self.track_check_box(check_box)

    def track_action(self, action):
        if action is None or bool(action.property("_oplog_action_tracked")):
            return

        action.setProperty("_oplog_action_tracked", True)
        action.triggered.connect(lambda checked=False, target=action: self.log_action(target, checked))

    def track_button(self, button):
        if button is None or isinstance(button, QtWidgets.QCheckBox):
            return
        if bool(button.property("_oplog_button_tracked")):
            return

        button.setProperty("_oplog_button_tracked", True)
        button.clicked.connect(lambda checked=False, target=button: self.log_button(target, checked))

    def track_line_edit(self, line_edit):
        if line_edit is None or bool(line_edit.property("_oplog_line_edit_tracked")):
            return

        line_edit.setProperty("_oplog_line_edit_tracked", True)
        line_edit.setProperty("_oplog_focus_text", line_edit.text())
        line_edit.setProperty("_oplog_user_edited", False)
        line_edit.textEdited.connect(
            lambda _text, target=line_edit: target.setProperty("_oplog_user_edited", True)
            if self._is_valid(target) else None
        )
        line_edit.editingFinished.connect(
            lambda target=line_edit: self._log_line_edit_if_changed(target)
            if self._is_valid(target) else None
        )

    def track_combo_box(self, combo_box):
        if combo_box is None or bool(combo_box.property("_oplog_combo_box_tracked")):
            return

        combo_box.setProperty("_oplog_combo_box_tracked", True)
        combo_box.activated.connect(
            lambda index, target=combo_box: self.log_combo_box(target, index)
        )

    def track_check_box(self, check_box):
        if check_box is None or bool(check_box.property("_oplog_check_box_tracked")):
            return

        check_box.setProperty("_oplog_check_box_tracked", True)
        check_box.clicked.connect(
            lambda checked, target=check_box: self.log_check_box(target, checked)
        )

    def eventFilter(self, watched, event):
        self._auto_track_object(watched)

        if event.type() == QtCore.QEvent.ChildAdded and hasattr(event, "child"):
            self._auto_track_object(event.child())

        if isinstance(watched, QtWidgets.QLineEdit) and self._is_valid(watched):
            if event.type() == QtCore.QEvent.FocusIn:
                watched.setProperty("_oplog_focus_text", watched.text())
                watched.setProperty("_oplog_user_edited", False)
            elif event.type() == QtCore.QEvent.FocusOut:
                self._log_line_edit_if_changed(watched)

        return super(OperationLogger, self).eventFilter(watched, event)

    def log_button(self, button, checked=None):
        if not self._is_valid(button):
            return
        data = {
            "type": "button",
            "window": self._get_window_title(button),
            "button_text": self._get_widget_text(button),
            "object_name": self._get_object_name(button),
        }
        if button.isCheckable():
            data["checked"] = button.isChecked() if checked is None else checked
        self._write_log(data)

    def log_action(self, action, checked=None):
        if not self._is_valid(action):
            return
        data = {
            "type": "action",
            "window": self._get_window_title(action),
            "action_text": self._get_action_text(action),
            "object_name": self._get_object_name(action),
        }
        if action.isCheckable():
            data["checked"] = action.isChecked() if checked is None else checked
        self._write_log(data)

    def log_combo_box(self, combo_box, index):
        if not self._is_valid(combo_box):
            return
        data = {
            "type": "combo_box",
            "window": self._get_window_title(combo_box),
            "object_name": self._get_object_name(combo_box),
            "current_index": combo_box.currentIndex() if index is None else index,
            "current_text": combo_box.currentText(),
        }
        self._write_log(data)

    def log_check_box(self, check_box, checked):
        if not self._is_valid(check_box):
            return
        data = {
            "type": "check_box",
            "window": self._get_window_title(check_box),
            "object_name": self._get_object_name(check_box),
            "check_box_text": self._get_widget_text(check_box),
            "checked": bool(checked),
        }
        self._write_log(data)

    def _log_line_edit_if_changed(self, line_edit):
        if not self._is_valid(line_edit):
            return

        user_edited = bool(line_edit.property("_oplog_user_edited"))
        before_text = line_edit.property("_oplog_focus_text")
        after_text = line_edit.text()

        if before_text is None:
            before_text = ""
        if not user_edited or before_text == after_text:
            return

        data = {
            "type": "line_edit",
            "window": self._get_window_title(line_edit),
            "object_name": self._get_object_name(line_edit),
            "before": before_text,
            "after": after_text,
        }
        self._write_log(data)
        line_edit.setProperty("_oplog_focus_text", after_text)
        line_edit.setProperty("_oplog_user_edited", False)

    def _auto_track_object(self, obj):
        if obj is None:
            return

        if isinstance(obj, QtWidgets.QAction):
            self.track_action(obj)
            return

        if isinstance(obj, QtWidgets.QCheckBox):
            self.track_check_box(obj)
            return

        if isinstance(obj, QtWidgets.QComboBox):
            self.track_combo_box(obj)
            return

        if isinstance(obj, QtWidgets.QLineEdit):
            self.track_line_edit(obj)
            return

        if isinstance(obj, QtWidgets.QAbstractButton):
            self.track_button(obj)

    def _write_log(self, data):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        parts = [f"[{timestamp}]"]
        for key, value in data.items():
            parts.append(f"{key}={self._format_value(value)}")
        line = " ".join(parts)

        log_file_path = os.path.join(
            self.log_dir,
            datetime.datetime.now().strftime("%Y-%m-%d") + ".log"
        )
        with self._write_lock:
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(line + "\n")

    def _format_value(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "\"\""
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value), ensure_ascii=False)

    def _is_valid(self, obj):
        """检查 Qt 对象的 C++ 底层是否仍然存活，防止 use-after-free 崩溃。"""
        if obj is None:
            return False
        try:
            return not sip.isdeleted(obj)
        except Exception:
            return False

    def _get_object_name(self, obj):
        if obj is None:
            return "<no-object>"
        name = obj.objectName() if hasattr(obj, "objectName") else ""
        return name or "<no-object-name>"

    def _get_widget_text(self, widget):
        if widget is None or not hasattr(widget, "text"):
            return ""
        return widget.text().strip()

    def _get_action_text(self, action):
        if action is None:
            return ""
        return action.text().replace("&", "").strip()

    def _get_window_title(self, obj):
        widget = None

        if isinstance(obj, QtWidgets.QWidget):
            widget = obj
        elif isinstance(obj, QtWidgets.QAction):
            for associated_widget in obj.associatedWidgets():
                if associated_widget is not None:
                    widget = associated_widget
                    break
            if widget is None:
                parent = obj.parent()
                if isinstance(parent, QtWidgets.QWidget):
                    widget = parent

        if widget is None:
            return ""

        if not self._is_valid(widget):
            return ""

        window = widget.window()
        if window is None:
            return ""
        return window.windowTitle().strip()
