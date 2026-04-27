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
        except Exception as error:
            if self._should_retry_exception(error) and self._reconnect():
                return func(self, *args, **kwargs)
            raise

    return wrapper


class MUNPowerSupply(object):
    DEFAULT_BAUDRATE = 9600
    DEFAULT_VOLTAGE_SCALE = 100
    DEFAULT_CURRENT_SCALE = 1000

    def __init__(self, channel_count=3, slave_address=1, voltage_scale=DEFAULT_VOLTAGE_SCALE, current_scale=DEFAULT_CURRENT_SCALE):
        self.channel_count = max(2, min(10, int(channel_count)))
        self.slave_address = int(slave_address)
        self.voltage_scale = int(voltage_scale)
        self.current_scale = int(current_scale)
        # Protocol register map from "MU_N模块电源系列" 20250517:
        # Set U=N10, Set I=N11, OVP=N12, OVPen=N13, OCP=N14, OCPen=N15.
        self._set_voltage_offset = 10
        self._set_current_offset = 11
        self._over_voltage_offset = 12
        self._over_voltage_enable_offset = 13
        self._over_current_offset = 14
        self._over_current_enable_offset = 15

        self.lock = threading.RLock()
        self.serial = None
        self._resource_name = None
        self._read_timeout = 0.5
        self._write_timeout = 0.5

    @classmethod
    def list_available_resources(cls):
        resources = []
        for port in serial.tools.list_ports.comports():
            port_name = getattr(port, "device", "")
            if port_name:
                resources.append(port_name)
        return sorted(set(resources))

    @classmethod
    def get_environment_hint(cls):
        if cls.list_available_resources():
            return "Modbus RTU 默认配置：9600 波特率，地址 1。"
        return "未检测到可用串口设备。请检查 USB 串口驱动和设备连接。"

    def open(self, resource_name, read_timeout=0.5, write_timeout=0.5):
        resource_name = str(resource_name).strip()
        if not resource_name:
            raise RuntimeError("Empty resource name")

        self._resource_name = resource_name
        self._read_timeout = float(read_timeout)
        self._write_timeout = float(write_timeout)
        self.serial = serial.Serial(
            port=resource_name,
            baudrate=self.DEFAULT_BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self._read_timeout,
            write_timeout=self._write_timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        self._reset_buffers()

    def close(self):
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.close()
            self.serial = None

    def _should_retry_exception(self, error):
        return isinstance(error, (serial.SerialException, TimeoutError))

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
                self.open(self._resource_name, self._read_timeout, self._write_timeout)
                return True
            except Exception:
                return False

    def _ensure_open(self):
        if self.serial is None or not self.serial.is_open:
            raise serial.SerialException("Serial port is not open")

    def _reset_buffers(self):
        if self.serial is None:
            return
        if hasattr(self.serial, "reset_input_buffer"):
            self.serial.reset_input_buffer()
        if hasattr(self.serial, "reset_output_buffer"):
            self.serial.reset_output_buffer()

    @staticmethod
    def _crc16(payload):
        crc = 0xFFFF
        for byte in payload:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, byteorder="little")

    def _validate_channel(self, channel):
        channel = int(channel)
        if channel < 1 or channel > self.channel_count:
            raise RuntimeError(f"Invalid channel number: {channel}")
        return channel

    def _channel_base(self, channel):
        channel = self._validate_channel(channel)
        return channel * 100

    def _read_exact(self, size):
        self._ensure_open()
        data = self.serial.read(size)
        if len(data) != size:
            raise TimeoutError(f"Expected {size} bytes, got {len(data)}")
        return data

    def _transact(self, payload, expected_size):
        self._ensure_open()
        request = payload + self._crc16(payload)
        with self.lock:
            self._reset_buffers()
            self.serial.write(request)
            self.serial.flush()
            response = self._read_exact(expected_size)

        if response[:-2] == b"":
            raise RuntimeError("Empty response")
        response_crc = response[-2:]
        expected_crc = self._crc16(response[:-2])
        if response_crc != expected_crc:
            raise RuntimeError("CRC check failed")
        if response[0] != self.slave_address:
            raise RuntimeError(f"Unexpected slave address: {response[0]}")
        if response[1] & 0x80:
            raise RuntimeError(f"Modbus exception code: {response[2]}")
        return response

    def _read_holding_registers(self, start_register, count):
        payload = bytes(
            [
                self.slave_address,
                0x03,
                (start_register >> 8) & 0xFF,
                start_register & 0xFF,
                (count >> 8) & 0xFF,
                count & 0xFF,
            ]
        )
        response = self._transact(payload, expected_size=5 + 2 * count)
        byte_count = response[2]
        if byte_count != count * 2:
            raise RuntimeError(f"Unexpected byte count: {byte_count}")

        values = []
        for index in range(count):
            offset = 3 + index * 2
            values.append((response[offset] << 8) | response[offset + 1])
        return values

    def _write_single_register(self, register, value):
        value = int(value) & 0xFFFF
        payload = bytes(
            [
                self.slave_address,
                0x06,
                (register >> 8) & 0xFF,
                register & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF,
            ]
        )
        response = self._transact(payload, expected_size=8)
        if response[:6] != payload:
            raise RuntimeError("Unexpected write response")

    def _write_multiple_registers(self, start_register, values):
        values = [int(value) & 0xFFFF for value in values]
        byte_count = len(values) * 2
        payload = bytearray(
            [
                self.slave_address,
                0x10,
                (start_register >> 8) & 0xFF,
                start_register & 0xFF,
                (len(values) >> 8) & 0xFF,
                len(values) & 0xFF,
                byte_count,
            ]
        )
        for value in values:
            payload.extend([(value >> 8) & 0xFF, value & 0xFF])

        response = self._transact(bytes(payload), expected_size=8)
        if response[2] != ((start_register >> 8) & 0xFF) or response[3] != (start_register & 0xFF):
            raise RuntimeError("Unexpected write response")

    def _to_register_value(self, value, scale):
        value = float(value)
        if value < 0:
            raise RuntimeError(f"Invalid negative value: {value}")
        return int(round(value * scale))

    def _from_register_value(self, value, scale):
        return float(value) / float(scale)

    @_auto_reconnect
    def get_idn(self):
        if self._resource_name:
            return f"MU_N {self.channel_count}CH @ {self._resource_name}"
        return f"MU_N {self.channel_count}CH"

    @_auto_reconnect
    def enableOutput(self, enable=True, channel=None):
        if channel is None:
            self._write_single_register(0x0000, 0x0001 if enable else 0x0000)
            return
        channel_register = self._channel_base(channel)
        self._write_single_register(channel_register, 0x0001 if enable else 0x0000)

    @_auto_reconnect
    def setVoltage(self, channel, voltage):
        register = self._channel_base(channel) + self._set_voltage_offset
        self._write_single_register(register, self._to_register_value(voltage, self.voltage_scale))

    @_auto_reconnect
    def getVoltage(self, channel):
        register = self._channel_base(channel) + self._set_voltage_offset
        value = self._read_holding_registers(register, 1)[0]
        return self._from_register_value(value, self.voltage_scale)

    @_auto_reconnect
    def setCurrent(self, channel, current):
        register = self._channel_base(channel) + self._set_current_offset
        self._write_single_register(register, self._to_register_value(current, self.current_scale))

    @_auto_reconnect
    def getCurrent(self, channel):
        register = self._channel_base(channel) + self._set_current_offset
        value = self._read_holding_registers(register, 1)[0]
        return self._from_register_value(value, self.current_scale)

    def _voltage_limit_register(self, channel):
        return self._channel_base(channel) + self._over_voltage_offset

    def _voltage_limit_enable_register(self, channel):
        return self._channel_base(channel) + self._over_voltage_enable_offset

    @_auto_reconnect
    def setVoltageLimitEnabled(self, channel, enabled):
        register = self._voltage_limit_enable_register(channel)
        self._write_single_register(register, 0x0001 if enabled else 0x0000)

    @_auto_reconnect
    def getVoltageLimitEnabled(self, channel):
        register = self._voltage_limit_enable_register(channel)
        return bool(self._read_holding_registers(register, 1)[0])

    @_auto_reconnect
    def setVoltageLimit(self, channel, voltage_limit):
        voltage_limit = float(voltage_limit)
        register = self._voltage_limit_register(channel)
        self._write_single_register(register, self._to_register_value(max(voltage_limit, 0.0), self.voltage_scale))
        self.setVoltageLimitEnabled(channel, voltage_limit > 0)

    @_auto_reconnect
    def getVoltageLimit(self, channel):
        register = self._voltage_limit_register(channel)
        value = self._read_holding_registers(register, 1)[0]
        if not self.getVoltageLimitEnabled(channel):
            return 0.0
        return self._from_register_value(value, self.voltage_scale)

    def _current_limit_register(self, channel):
        return self._channel_base(channel) + self._over_current_offset

    def _current_limit_enable_register(self, channel):
        return self._channel_base(channel) + self._over_current_enable_offset

    @_auto_reconnect
    def setCurrentLimitEnabled(self, channel, enabled):
        register = self._current_limit_enable_register(channel)
        self._write_single_register(register, 0x0001 if enabled else 0x0000)

    @_auto_reconnect
    def getCurrentLimitEnabled(self, channel):
        register = self._current_limit_enable_register(channel)
        return bool(self._read_holding_registers(register, 1)[0])

    @_auto_reconnect
    def setCurrentLimit(self, channel, current_limit):
        current_limit = float(current_limit)
        register = self._current_limit_register(channel)
        self._write_single_register(register, self._to_register_value(max(current_limit, 0.0), self.current_scale))
        self.setCurrentLimitEnabled(channel, current_limit > 0)

    @_auto_reconnect
    def getCurrentLimit(self, channel):
        register = self._current_limit_register(channel)
        value = self._read_holding_registers(register, 1)[0]
        if not self.getCurrentLimitEnabled(channel):
            return 0.0
        return self._from_register_value(value, self.current_scale)

    @_auto_reconnect
    def getVoltageOutput(self, channel):
        register = self._channel_base(channel) + 6
        value = self._read_holding_registers(register, 2)[0]
        return self._from_register_value(value, self.voltage_scale)

    @_auto_reconnect
    def getCurrentOutput(self, channel):
        register = self._channel_base(channel) + 6
        value = self._read_holding_registers(register, 2)[1]
        return self._from_register_value(value, self.current_scale)

    @_auto_reconnect
    def getOutput(self):
        values = []
        for channel in range(1, self.channel_count + 1):
            register = self._channel_base(channel) + 6
            voltage, current = self._read_holding_registers(register, 2)
            values.append(
                [
                    self._from_register_value(voltage, self.voltage_scale),
                    self._from_register_value(current, self.current_scale),
                ]
            )
        return values
