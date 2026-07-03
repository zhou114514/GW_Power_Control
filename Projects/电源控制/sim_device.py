"""
内置"虚拟设备/模拟设备"支持，用于无硬件调试。

思路：四个驱动的串口 I/O 都经由 self.serial。本模块提供两个"长得像串口"的
假传输对象，驱动 open() 检测到 SIM 端口名时把 self.serial 换成假对象即可，
其余驱动/控件/采集/画图/CSV/总控/TCP 逻辑完全不改。

保真度（中等）：
  - 设定电压/电流、输出开关、通道使能、限值都记忆并可回读；
  - 实测值：输出关=0；输出开后在 RAMP_SECONDS 内从 0 线性爬升到设定值，
    之后设定值叠加微小噪声/纹波；
  - 不做故障注入。
"""

import random
import re
import time

# 端口下拉里常驻的虚拟设备名
SIM_PORT_NAME = "SIM 虚拟设备"
# 上电后实测值爬升到设定值所需时间（秒）
RAMP_SECONDS = 1.5


def is_sim_port(name):
    """判断给定端口/资源名是否为虚拟设备。"""
    return str(name or "").strip() == SIM_PORT_NAME


def _noise(magnitude):
    if magnitude <= 0:
        return 0.0
    return random.uniform(-magnitude, magnitude)


def _ramp_measure(setpoint, output_on, t_on):
    """按中等保真规则计算一个实测值。"""
    if not output_on:
        return 0.0
    frac = 1.0
    if t_on:
        frac = min(1.0, max(0.0, (time.time() - t_on) / RAMP_SECONDS))
    value = float(setpoint) * frac
    return max(0.0, value + _noise(max(abs(value) * 0.003, 0.003)))


class FakeScpiSerial(object):
    """模拟 GPD / PSW / GPP 文本协议的假串口。"""

    def __init__(self, device_type):
        self.device_type = str(device_type).upper()
        self.is_open = True
        self.timeout = 1

        if self.device_type == "GPD":
            self.channels = [1, 2]
            self.term = b"\r"
            self.idn = "GW-INSTEK,GPD-3303S-SIM,SN00000001,V1.00"
        elif self.device_type == "PSW":
            self.channels = [1]
            self.term = b"\n"
            self.idn = "GW-INSTEK,PSW-SIM,SN00000001,V1.00"
        else:  # GPP
            self.channels = [1, 2, 3]
            self.term = b"\n"
            self.idn = "GW-INSTEK,GPP-SIM,SN00000001,V1.00"

        self.vset = {ch: 0.0 for ch in self.channels}
        self.iset = {ch: 0.0 for ch in self.channels}
        self.output = {ch: False for ch in self.channels}
        self.t_on = {ch: 0.0 for ch in self.channels}
        self._out = []  # 待读取的响应队列（每项一整行 bytes）

    # ------- serial-like API -------
    def write(self, data):
        try:
            cmd = bytes(data).decode("ascii", errors="ignore").strip()
        except Exception:
            return
        if cmd:
            self._handle(cmd)

    def flush(self):
        pass

    def readline(self, *args, **kwargs):
        return self._out.pop(0) if self._out else b""

    def read(self, size=1):
        return b""

    def reset_input_buffer(self):
        self._out = []

    def reset_output_buffer(self):
        pass

    def close(self):
        self.is_open = False

    # ------- helpers -------
    def _reply(self, text):
        self._out.append(text.encode("ascii") + self.term)

    def _set_output(self, ch, on):
        if ch not in self.output:
            return
        if on and not self.output[ch]:
            self.t_on[ch] = time.time()
        self.output[ch] = on

    def _measured(self, ch, setpoint):
        return _ramp_measure(setpoint, self.output.get(ch, False), self.t_on.get(ch, 0.0))

    # ------- command dispatch -------
    def _handle(self, cmd):
        cu = cmd.upper()

        if cu.startswith("*IDN?"):
            self._reply(self.idn)
            return
        if cu.startswith("ERR?"):
            self._reply("No Error.")
            return
        if cu.startswith("SYST") and "ERR" in cu and cu.endswith("?"):
            self._reply('+0,"No error"')
            return

        # VSET<ch>:<val> / ISET<ch>:<val>
        m = re.match(r"^([VI])SET(\d+):([-+0-9.eE]+)$", cu)
        if m:
            ch, val = int(m.group(2)), float(m.group(3))
            target = self.vset if m.group(1) == "V" else self.iset
            if ch in target:
                target[ch] = val
            return
        # VSET<ch>? / ISET<ch>?
        m = re.match(r"^([VI])SET(\d+)\?$", cu)
        if m:
            ch = int(m.group(2))
            src = self.vset if m.group(1) == "V" else self.iset
            self._reply("%.3f" % src.get(ch, 0.0))
            return
        # VOUT<ch>? / IOUT<ch>?  (实测)
        m = re.match(r"^([VI])OUT(\d+)\?$", cu)
        if m:
            ch = int(m.group(2))
            sp = (self.vset if m.group(1) == "V" else self.iset).get(ch, 0.0)
            self._reply("%.3f" % self._measured(ch, sp))
            return

        # PSW: APPLy <v>,<i>
        m = re.match(r"^APPL[Y]?\s+([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)$", cu)
        if m:
            self.vset[1] = float(m.group(1))
            self.iset[1] = float(m.group(2))
            return
        # PSW: APPLy?
        if cu.startswith("APPL") and cu.endswith("?"):
            self._reply("%.3f,%.3f" % (self.vset.get(1, 0.0), self.iset.get(1, 0.0)))
            return

        # PSW: MEASure[:SCALar]:VOLTage|CURRent|POWer[:DC]?
        if cu.startswith("MEAS") or cu.startswith(":MEAS"):
            ch = 1
            mm = re.search(r"MEAS\w*?(\d)", cu)
            if mm:
                ch = int(mm.group(1))
            if "VOLT" in cu:
                self._reply("%.3f" % self._measured(ch, self.vset.get(ch, 0.0)))
            elif "CURR" in cu:
                self._reply("%.3f" % self._measured(ch, self.iset.get(ch, 0.0)))
            elif "POW" in cu:
                v = self._measured(ch, self.vset.get(ch, 0.0))
                i = self._measured(ch, self.iset.get(ch, 0.0))
                self._reply("%.3f" % (v * i))
            else:
                self._reply("0.000")
            return

        # GPD: OUT1 / OUT0（全局）
        m = re.match(r"^OUT([01])$", cu)
        if m:
            on = m.group(1) == "1"
            for ch in self.channels:
                self._set_output(ch, on)
            return
        # GPP: :OUTPut<ch>:STATe {0|1|ON|OFF}（分通道）
        m = re.match(r"^:?OUTP\w*(\d):STAT\w*\s+(ON|OFF|1|0)$", cu)
        if m:
            self._set_output(int(m.group(1)), m.group(2) in ("ON", "1"))
            return
        # GPP: :ALLOUTON / :ALLOUTOFF
        if cu.startswith(":ALLOUTON"):
            for ch in self.channels:
                self._set_output(ch, True)
            return
        if cu.startswith(":ALLOUTOFF"):
            for ch in self.channels:
                self._set_output(ch, False)
            return
        # PSW: OUTPut {0|1|ON|OFF}（全局，无分通道，无前导冒号）
        m = re.match(r"^OUTP\w*\s+(ON|OFF|1|0)$", cu)
        if m:
            on = m.group(1) in ("ON", "1")
            for ch in self.channels:
                self._set_output(ch, on)
            return

        # 其它命令（TRACK/BEEP/OVP/OCP/SAV/RCL/set series 等）：静默接受，不回复
        return


class FakeModbusSerial(object):
    """模拟 MU_N 模块电源的 Modbus RTU 假串口（功能码 0x03/0x06/0x10）。"""

    def __init__(self, channel_count=3, slave_address=1):
        self.is_open = True
        self.timeout = 1
        self.slave = int(slave_address)
        self.channel_count = int(channel_count)
        self.reg = {}          # 寄存器 -> 原始 int 值
        self.t_on = {}         # 通道 -> 上电时刻
        self._out = bytearray()  # 待读取字节

    # ------- serial-like API -------
    def write(self, data):
        self._respond(bytes(data))

    def flush(self):
        pass

    def read(self, size=1):
        chunk = bytes(self._out[:size])
        del self._out[:size]
        return chunk

    def readline(self, *args, **kwargs):
        data = bytes(self._out)
        self._out = bytearray()
        return data

    def reset_input_buffer(self):
        self._out = bytearray()

    def reset_output_buffer(self):
        pass

    def close(self):
        self.is_open = False

    # ------- helpers -------
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

    def _channel_on(self, ch):
        return bool(self.reg.get(ch * 100 + 0, 0)) or bool(self.reg.get(0x0000, 0))

    def _measured_reg(self, ch, offset):
        if not self._channel_on(ch):
            return 0
        setpoint_reg = self.reg.get(ch * 100 + (10 if offset == 6 else 11), 0)
        return int(_ramp_measure(setpoint_reg, True, self.t_on.get(ch, 0.0)))

    def _get_reg(self, register):
        offset = register % 100
        if offset in (6, 7):
            return self._measured_reg(register // 100, offset)
        return self.reg.get(register, 0)

    def _set_reg(self, register, value):
        value &= 0xFFFF
        if register == 0x0000:  # 全局使能
            if value:
                for ch in range(1, self.channel_count + 1):
                    self.t_on[ch] = time.time()
            self.reg[register] = value
            return
        if register % 100 == 0:  # 通道使能寄存器
            if value and not self.reg.get(register, 0):
                self.t_on[register // 100] = time.time()
        self.reg[register] = value

    def _respond(self, req):
        if len(req) < 6:
            return
        func = req[1]
        if func == 0x03:  # 读保持寄存器
            start = (req[2] << 8) | req[3]
            count = (req[4] << 8) | req[5]
            body = bytearray([self.slave, 0x03, count * 2])
            for i in range(count):
                v = self._get_reg(start + i) & 0xFFFF
                body += bytes([(v >> 8) & 0xFF, v & 0xFF])
            body += self._crc16(bytes(body))
            self._out += body
        elif func == 0x06:  # 写单个寄存器
            reg = (req[2] << 8) | req[3]
            val = (req[4] << 8) | req[5]
            self._set_reg(reg, val)
            resp = bytes(req[:6]) + self._crc16(bytes(req[:6]))
            self._out += resp
        elif func == 0x10:  # 写多个寄存器
            start = (req[2] << 8) | req[3]
            qty = (req[4] << 8) | req[5]
            for i in range(qty):
                hi, lo = req[7 + i * 2], req[8 + i * 2]
                self._set_reg(start + i, (hi << 8) | lo)
            head = bytes([self.slave, 0x10, req[2], req[3], req[4], req[5]])
            self._out += head + self._crc16(head)


def make_fake_serial(device_type, **kwargs):
    """按设备类型返回对应的假串口对象。"""
    dt = str(device_type).upper()
    if dt == "MU_N":
        return FakeModbusSerial(
            channel_count=kwargs.get("channel_count", 3),
            slave_address=kwargs.get("slave_address", 1),
        )
    return FakeScpiSerial(dt)
