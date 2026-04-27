import functools
import threading
import time

import serial
import serial.tools.list_ports


def _auto_reconnect(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            if self._should_retry_exception(e) and self._reconnect():
                return func(self, *args, **kwargs)
            raise

    return wrapper


class GPPPowerSupply(object):
    CH3_ALLOWED_VOLTAGES = (1.8, 2.5, 3.3, 5.0)

    def __init__(self):
        self.__baudRate = 115200
        self.__parityBit = serial.PARITY_NONE
        self.__dataBit = serial.EIGHTBITS
        self.__stopBit = serial.STOPBITS_ONE
        self.lock = threading.RLock()

        self._resource_name = None
        self._resource_type = None
        self._read_timeout = 1
        self._write_timeout = 1
        self._supports_iout3 = True

        self.serial = None
        self._visa_rm = None
        self._visa_inst = None
        self._visa_error_type = tuple()

    @staticmethod
    def _load_pyvisa():
        try:
            import pyvisa
        except Exception:
            return None
        return pyvisa

    @classmethod
    def list_serial_resources(cls):
        resources = []
        for port in serial.tools.list_ports.comports():
            port_name = getattr(port, "device", "")
            if port_name:
                resources.append(port_name)
        return sorted(set(resources))

    @classmethod
    def list_usb_resources(cls):
        pyvisa = cls._load_pyvisa()
        if pyvisa is None:
            return []

        rm = None
        try:
            rm = pyvisa.ResourceManager()
            resources = []
            for item in rm.list_resources():
                upper_item = item.upper()
                if upper_item.startswith("USB") and upper_item.endswith("INSTR"):
                    resources.append(item)
            return sorted(set(resources))
        except Exception:
            return []
        finally:
            try:
                if rm is not None:
                    rm.close()
            except Exception:
                pass

    @classmethod
    def list_available_resources(cls):
        return cls.list_serial_resources() + cls.list_usb_resources()

    @classmethod
    def get_environment_hint(cls):
        if cls.list_available_resources():
            return ""

        if cls._load_pyvisa() is None:
            return "未检测到可用设备。USB 连接 GPP 需要安装 pyvisa 和 VISA 运行库，或改用串口连接。"

        return "未检测到可用的串口或 USB VISA 资源。请检查 USB 连接、驱动和 VISA 运行库。"

    @staticmethod
    def is_usb_resource(resource_name):
        text = str(resource_name or "").strip().upper()
        return text.startswith("USB") and text.endswith("INSTR")

    def open(self, resource_name, readTimeOut=1, writeTimeOut=1):
        resource_name = str(resource_name).strip()
        if not resource_name:
            raise RuntimeError("Empty resource name")

        self._resource_name = resource_name
        self._read_timeout = readTimeOut
        self._write_timeout = writeTimeOut
        self._supports_iout3 = True

        if self.is_usb_resource(resource_name):
            self._resource_type = "visa"
            self._open_visa(resource_name, readTimeOut)
        else:
            self._resource_type = "serial"
            self._open_serial(resource_name, readTimeOut, writeTimeOut)

        idn = self.get_idn()
        if "GPP" not in idn.upper():
            self.close()
            raise RuntimeError(f"Unexpected device id: {idn}")

    def _open_serial(self, port, read_timeout, write_timeout):
        self.serial = serial.Serial(
            port=port,
            baudrate=self.__baudRate,
            bytesize=self.__dataBit,
            parity=self.__parityBit,
            stopbits=self.__stopBit,
            timeout=read_timeout,
            write_timeout=write_timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

        if hasattr(self.serial, "reset_input_buffer"):
            self.serial.reset_input_buffer()
        if hasattr(self.serial, "reset_output_buffer"):
            self.serial.reset_output_buffer()

    def _open_visa(self, resource_name, read_timeout):
        pyvisa = self._load_pyvisa()
        if pyvisa is None:
            raise RuntimeError("USB 连接需要安装 pyvisa")

        self._visa_error_type = (pyvisa.errors.VisaIOError,)
        self._visa_rm = pyvisa.ResourceManager()
        self._visa_inst = self._visa_rm.open_resource(resource_name)
        self._visa_inst.timeout = max(int(read_timeout * 1000), 1000)
        self._visa_inst.read_termination = "\n"
        self._visa_inst.write_termination = "\n"
        try:
            self._visa_inst.clear()
        except Exception:
            pass

    def close(self):
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.close()
            self.serial = None

            try:
                if self._visa_inst is not None:
                    self._visa_inst.close()
            except Exception:
                pass
            self._visa_inst = None

            try:
                if self._visa_rm is not None:
                    self._visa_rm.close()
            except Exception:
                pass
            self._visa_rm = None

    def _should_retry_exception(self, error):
        if isinstance(error, serial.SerialException):
            return True
        if self._visa_error_type and isinstance(error, self._visa_error_type):
            return True
        return False

    def _reconnect(self):
        if not self._resource_name:
            return False

        with self.lock:
            try:
                self.close()
            except Exception:
                pass

            time.sleep(0.3)
            try:
                if self._resource_type == "visa":
                    self._open_visa(self._resource_name, self._read_timeout)
                else:
                    self._open_serial(self._resource_name, self._read_timeout, self._write_timeout)
                return True
            except Exception:
                return False

    def _ensure_open(self):
        if self._resource_type == "visa":
            if self._visa_inst is None:
                raise RuntimeError("VISA resource is not open")
            return

        if self.serial is None or not self.serial.is_open:
            raise serial.SerialException("Serial port is not open")

    def _write(self, command):
        self._ensure_open()
        if self._resource_type == "visa":
            self._visa_inst.write(command)
            return

        payload = (command + "\n").encode("ascii")
        self.serial.write(payload)
        self.serial.flush()

    def _query(self, command):
        with self.lock:
            self._write(command)
            if self._resource_type == "visa":
                ret = self._visa_inst.read()
            else:
                ret = self.serial.readline()

        if ret in ("", b""):
            raise RuntimeError(f"No response for command: {command}")

        if isinstance(ret, bytes):
            return ret.decode(errors="ignore").strip()
        return str(ret).strip()

    def _parse_float(self, value):
        text = str(value).strip().upper()
        for suffix in ("V", "A", "W"):
            if text.endswith(suffix):
                text = text[:-1]
        return float(text.strip())

    def isValidChannel(self, channel):
        if channel not in (1, 2, 3):
            raise RuntimeError(f"Invalid channel number: {channel}")
        return True

    def isValidFloat(self, value):
        value = float(value)
        if value < 0:
            raise RuntimeError(f"Invalid float value: {value}")
        return True

    def isValidVoltage(self, channel, voltage):
        self.isValidChannel(channel)
        self.isValidFloat(voltage)
        if channel == 3:
            rounded = round(float(voltage), 1)
            if rounded not in self.CH3_ALLOWED_VOLTAGES:
                raise RuntimeError("CH3 only supports 1.8V / 2.5V / 3.3V / 5.0V")
        return True

    @_auto_reconnect
    def get_idn(self):
        return self._query("*IDN?")

    @_auto_reconnect
    def setVoltage(self, channel, voltage):
        self.isValidVoltage(channel, voltage)
        with self.lock:
            self._write(f"VSET{channel}:{float(voltage):.3f}")

    @_auto_reconnect
    def getVoltage(self, channel):
        self.isValidChannel(channel)
        ret = self._query(f"VSET{channel}?")
        return self._parse_float(ret)

    @_auto_reconnect
    def setCurrent(self, channel, current):
        self.isValidChannel(channel)
        if channel == 3:
            raise RuntimeError("CH3 current is fixed and cannot be set")
        self.isValidFloat(current)
        with self.lock:
            self._write(f"ISET{channel}:{float(current):.3f}")

    @_auto_reconnect
    def getCurrent(self, channel):
        self.isValidChannel(channel)
        if channel == 3:
            return 5.0
        ret = self._query(f"ISET{channel}?")
        return self._parse_float(ret)

    @_auto_reconnect
    def getVoltageOutput(self, channel):
        self.isValidChannel(channel)
        ret = self._query(f"VOUT{channel}?")
        return self._parse_float(ret)

    @_auto_reconnect
    def getCurrentOutput(self, channel):
        self.isValidChannel(channel)
        if channel == 3:
            if not self._supports_iout3:
                return 0.0
            try:
                ret = self._query("IOUT3?")
                return self._parse_float(ret)
            except Exception:
                self._supports_iout3 = False
                return 0.0
        ret = self._query(f"IOUT{channel}?")
        return self._parse_float(ret)

    @_auto_reconnect
    def enableOutput(self, enable=True, channel=None):
        with self.lock:
            if channel is None:
                self._write(":ALLOUTON" if enable else ":ALLOUTOFF")
            else:
                self.isValidChannel(channel)
                self._write(f":OUTPut{channel}:STATe {int(bool(enable))}")

    @_auto_reconnect
    def getOutput(self):
        result = []
        for channel in (1, 2, 3):
            result.append(
                [
                    self.getVoltageOutput(channel),
                    self.getCurrentOutput(channel),
                ]
            )
        return result
