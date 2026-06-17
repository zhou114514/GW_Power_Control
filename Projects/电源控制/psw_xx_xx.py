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
        pass

def _auto_reconnect(func):
    """装饰器：串口操作遇到SerialException时自动重连并重试一次，其它异常直接抛出"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except serial.SerialException as e:
            print(f"串口操作异常，尝试自动重连: {e}")
            if self._reconnect():
                return func(self, *args, **kwargs)
            raise
    return wrapper

class psw_xx_xx(object):
    def __init__(self):
        self.__baudRate = 9600 # 9600 bps
        self.__parityBit = 'N' # None
        self.__dataBit = 8
        self.__stopBit = 1
        self.__dataFlowControl = None
        self.eol = b'\n'
        self.serial = None
        self.voltage = None
        self.current = None
        self._command_termination = b'\n'
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
        
        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)

        # 检查分隔符是否正确设置。
        # 默认情况下，\r 是分隔符，但较新的 GPD3303S 使用 \r\n 作为分隔符。
        self.setTimeout(0.1)
        ret = self.serial.read(1)
        self.setTimeout(readTimeOut)
        
        if ret == b'\n':
            self.setDelimiter(b'\r\n')
    
    def close(self):
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.close()

    def _reconnect(self):
        """尝试关闭并重新打开串口"""
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
                self.serial = MySerial(
                    port         = self._port_name,
                    baudrate     = self.__baudRate,
                    bytesize     = self.__dataBit,
                    parity       = self.__parityBit,
                    stopbits     = self.__stopBit,
                    timeout      = self._read_timeout,
                    writeTimeout = self._write_timeout,
                    dsrdtr       = self.__dataFlowControl)
                print(f"串口{self._port_name}重连成功")
                return True
            except Exception as e:
                print(f"串口{self._port_name}重连失败: {e}")
                return False

    def setTimeout(self, timeout):
        if hasattr(self.serial, 'setTimeout') and \
           callable(getattr(self.serial, 'setTimeout')):
            # pySerial <= v2.7
            self.serial.setTimeout(timeout)
        else:
            # pySerial v3
            self.serial.timeout = timeout

    def _write_command(self, command):
        if isinstance(command, str):
            command = command.encode("ascii")
        command = command.rstrip(b"\r\n") + self._command_termination
        self.serial.write(command)
        self.serial.flush()

    def _query(self, command):
        self._write_command(command)
        ret = self.serial.readline()
        if ret == b"":
            raise RuntimeError("No response for command: %s" % command)
        return ret.decode(errors="ignore").strip()

    def _query_apply(self):
        ret = self._query("APPLy?")
        parts = [part.strip() for part in ret.split(",")]
        if len(parts) < 2:
            raise RuntimeError("Unexpected APPLy? response: %s" % ret)
        voltage = float(parts[0])
        current = float(parts[1])
        self.voltage = voltage
        self.current = current
        return voltage, current

    @_auto_reconnect
    def setVoltageCurrent(self, voltage, current):
        voltage = float(voltage)
        current = float(current)
        self.isValidFloat(voltage)
        self.isValidFloat(current)
        with self.lock:
            self._write_command("APPLy %.3f,%.3f" % (voltage, current))
            self.voltage = voltage
            self.current = current
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

    @_auto_reconnect
    def setCurrent(self, current):
        """
        APPLy self.voltage,current
        """
        current = float(current)
        self.isValidFloat(current)
        with self.lock:
            voltage = self.voltage
            if voltage is None:
                voltage, _ = self._query_apply()
            self._write_command("APPLy %.3f,%.3f" % (voltage, current))
            self.current = current

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)
        
    @_auto_reconnect
    def getCurrent(self):
        """
        APPLy?
        """
        with self.lock:
            _, current = self._query_apply()
            return current

    @_auto_reconnect
    def getVoltageCurrent(self):
        """
        APPLy? - query voltage and current settings in one request.
        """
        with self.lock:
            return self._query_apply()

    @_auto_reconnect
    def setVoltage(self, voltage):
        """
        APPLy voltage,self.current
        """
        voltage = float(voltage)
        self.isValidFloat(voltage)
        with self.lock:
            current = self.current
            if current is None:
                _, current = self._query_apply()
            self._write_command("APPLy %.3f,%.3f" % (voltage, current))
            self.voltage = voltage

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)
        
    @_auto_reconnect
    def getVoltage(self):
        """
        APPLy?
        """
        with self.lock:
            voltage, _ = self._query_apply()
            return voltage
    @_auto_reconnect
    def getCurrentOutput(self):
        """
        MEASure[:SCALar]:CURRent[:DC]?
        """
        with self.lock:
            self.serial.write(b'MEASure:CURRent?\r\n')
            self.serial.flush()
            ret = self.serial.readline()

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return float(ret.decode())


    @_auto_reconnect
    def getVoltageOutput(self):
        """
        MEASure[:SCALar]:VOLTage[:DC]? 
        """
        with self.lock:
            self.serial.write(b'MEASure:VOLTage?\n')
            self.serial.flush()
            ret = self.serial.readline()

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return float(ret.decode())
    

    @_auto_reconnect
    def getOutput(self):
        """
        MEASure[:SCALar]:VOLTage[:DC]?\n
        MEASure[:SCALar]:CURRent[:DC]?\n
        """
        # ntime = time.time()
        with self.lock:
            ret = {"电压":0, "电流":0}
            self.serial.write(b'MEASure:VOLTage?\n')
            v = self.serial.readline()
            self.serial.write(b'MEASure:CURRent?\n')
            i = self.serial.readline()
            # print(time.time() - ntime)

            ret["电压"], ret["电流"] = float(v.decode()), float(i.decode())

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return [ret["电压"], ret["电流"]]


    @_auto_reconnect
    def enableOutput(self, enable = True):
        """
        OUTPut <bool>
        """
        with self.lock:
            self.serial.write(b'OUTPut %d\n' % int(enable))

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)
        
    def getError(self):
        """
        SYSTem:ERRor?
        """
        with self.lock:
            self.serial.write(b'SYSTem:ERRor?\r\n')
            ret = self.serial.readline()
            if ret != b'':
                return ret[:-len(self.eol)]
            else:
                return b'+0,"No error"'
            

    def setDelimiter(self, eol = b'\r\n'):
        """
        Must call this method for new-firmware (2.0 or above?) instruments.
        Because the delimiter setting has been changed. 
        """
        self.eol = eol


if __name__ == '__main__':
    psw = psw_xx_xx()
    psw.open('COM32')
    v, i = psw.getOutput()
    print(v, i)
    psw.close()



