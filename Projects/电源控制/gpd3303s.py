"""
This is an interface module for DC Power Supply GPD-3303S manufactured by Good
Will Instrument Co., Ltd.
"""

import serial
import sys
import time
import threading
import functools

class MySerial(serial.Serial):
    """
    Wrapper for Serial
    """
    try:
        import io
    except ImportError:
        # serial.Serial inherits serial.FileLike
        pass
    else:
        def readline(self, eol=b'\r'):
            """
            重写 io.RawIOBase.readline 方法，该方法无法处理'\r'分隔符。
            """
            leneol = len(eol)
            ret = b''
            while True:
                c = self.read(1)
                if c:
                    ret += c
                    if ret[-leneol:] == eol:
                        break
                else:
                    break

            return ret

class GPD3303S(object):
    def __init__(self):
        self.__baudRate = 9600 # 9600 bps
        self.__parityBit = 'N' # None
        self.__dataBit = 8
        self.__stopBit = 1
        self.__dataFlowControl = None
        self.eol = b'\r'
        self.serial = None
        self.lock = threading.RLock()
        self._port_name = None
        self._read_timeout = 1
        self._write_timeout = 1

    def open(self, port, readTimeOut = 1, writeTimeOut = 1):
        self._port_name = port
        self._read_timeout = readTimeOut
        self._write_timeout = writeTimeOut
        self.serial = MySerial(port         = port,
                               baudrate     = self.__baudRate,
                               bytesize     = self.__dataBit,
                               parity       = self.__parityBit,
                               stopbits     = self.__stopBit,
                               timeout      = readTimeOut,
                               writeTimeout = writeTimeOut,
                               dsrdtr       = self.__dataFlowControl)
        
        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        # 当前实机返回格式是“前导 \\n + 结尾 \\r”。
        # 旧逻辑在读到残留的换行符后把结束符切成 \\r\\n，
        # 会导致后续 VSET?/IOUT? 读取错位，进而被误判为连接失败。
        # 这里保留以 \\r 作为结束符，只把可能残留的单个换行读走。
        self.setDelimiter(b'\r')
        self.setTimeout(0.1)
        try:
            if self.serial.read(1) not in (b'', b'\n'):
                if hasattr(self.serial, 'reset_input_buffer'):
                    self.serial.reset_input_buffer()
        finally:
            self.setTimeout(readTimeOut)
    
    def close(self):
        if self.serial is not None:
            self.serial.close()

    def setTimeout(self, timeout):
        if hasattr(self.serial, 'setTimeout') and \
           callable(getattr(self.serial, 'setTimeout')):
            # pySerial <= v2.7
            self.serial.setTimeout(timeout)
        else:
            # pySerial v3
            self.serial.timeout = timeout

    def _reconnect(self):
        """尝试关闭并重新打开串口，供 _auto_reconnect 调用。"""
        if not self._port_name:
            return False
        with self.lock:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()
            except Exception:
                pass
            time.sleep(0.5)
            try:
                self.open(self._port_name, self._read_timeout, self._write_timeout)
                print("GPD 串口%s重连成功" % self._port_name)
                return True
            except Exception as e:
                print("GPD 串口%s重连失败: %s" % (self._port_name, e))
                return False

    def _parseReading(self, ret, unit=b''):
        """
        解析一条读数响应为浮点数。
        空响应或非数字响应都视为通信异常（SerialException），
        以便 _auto_reconnect 触发重连重试，而不是抛出会杀死采集线程的 ValueError。
        """
        if not ret:
            raise serial.SerialException('GPD 无响应（空读取）')
        text = ret
        if self.eol and text.endswith(self.eol):
            text = text[:-len(self.eol)]
        text = text.replace(unit, b'').strip()
        try:
            return float(text)
        except ValueError:
            raise serial.SerialException('GPD 读数无法解析: %r' % ret)

    def isValidChannel(self, channel):
        """
        检查通道号是否有效。只能是1或2。
        """
        if not (channel == 1 or channel == 2):
            raise RuntimeError('Invalid channel number: %d was given.' % channel)

        return True

    def isValidFloat(self, value):
        """
        检查给定的浮点数是否有效。允许三位以下有效数字。
        """
        if value < 0:
            raise RuntimeError('Invalid float value: %f was given.' % value)
        
        str = "%f" % value
        position = str.find(".")
        maxDigits = 5
        if 0 <= position and position <= maxDigits : # found
            str = str[0:maxDigits + 1]
        else: # not found
            str = str[0:maxDigits]

        if float(str) != value:
            sys.stderr.write('Invalid float value: %f was given.' % value)
            return False
        
        return True

    def setCurrent(self, channel, current):
        """
        ISET<X>:<NR2>
        """
        self.isValidChannel(channel)
        self.serial.write(b'ISET%d:%.3f\n' % (channel, current))

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)
        
    def getCurrent(self, channel):
        """
        ISET<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'ISET%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return self._parseReading(ret, b'A')

    def setVoltage(self, channel, voltage):
        """
        VSET<X>:<NR2>
        """
        self.isValidChannel(channel)
        self.serial.write(b'VSET%d:%.3f\n' % (channel, voltage))

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)
        
    def getVoltage(self, channel):
        """
        VSET<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'VSET%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return self._parseReading(ret, b'V')

    def getCurrentOutput(self, channel):
        """
        IOUT<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'IOUT%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return self._parseReading(ret, b'A')

    def getVoltageOutput(self, channel):
        """
        VOUT<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'VOUT%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return self._parseReading(ret, b'V')

    def enableOutput(self, enable = True):
        """
        OUT<Boolean>
        """
        self.serial.write(b'OUT%d\n' % int(enable))

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)
        
    def getError(self):
        """
        ERR?
        """
        self.serial.write(b'ERR?\n')
        ret = self.serial.readline(eol=self.eol)
        if ret != b'':
            return ret[:-len(self.eol)].strip()
        else:
            # 空响应视为通信异常，让调用方的 _auto_reconnect 触发重连
            raise serial.SerialException('Cannot read error message (empty)')
        

    def setDelimiter(self, eol = b'\r\n'):
        """
        Must call this method for new-firmware (2.0 or above?) instruments.
        Because the delimiter setting has been changed. 
        """
        self.eol = eol


def _locked_serial_transaction(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper


def _auto_reconnect(method):
    """串口操作遇到 SerialException 时自动重连并重试一次，其它异常直接抛出。"""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except serial.SerialException as e:
            print("GPD 串口操作异常，尝试自动重连: %s" % e)
            if self._reconnect():
                return method(self, *args, **kwargs)
            raise
    return wrapper


# 仅加锁（不自动重连）：连接管理与错误查询本身
for _method_name in ("open", "close", "getError"):
    setattr(
        GPD3303S,
        _method_name,
        _locked_serial_transaction(getattr(GPD3303S, _method_name)),
    )

# 加锁 + 自动重连：真正的数据读写方法
for _method_name in (
    "setCurrent",
    "getCurrent",
    "setVoltage",
    "getVoltage",
    "getCurrentOutput",
    "getVoltageOutput",
    "enableOutput",
):
    setattr(
        GPD3303S,
        _method_name,
        _auto_reconnect(_locked_serial_transaction(getattr(GPD3303S, _method_name))),
    )

del _method_name

