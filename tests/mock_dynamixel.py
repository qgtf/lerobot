"""Mocked classes and functions from dynamixel_sdk to allow for continuous integration
and testing code logic that requires hardware and devices (e.g. robot arms, cameras)

Warning: These mocked versions are minimalist. They do not exactly mock every behaviors
from the original classes and functions (e.g. return types might be None instead of boolean).
"""

from dynamixel_sdk import COMM_SUCCESS

DEFAULT_BAUDRATE = 9_600


def mock_convert_to_bytes(value, bytes):
    # TODO(rcadene): remove need to mock `convert_to_bytes` by implemented the inverse transform
    # `convert_bytes_to_value`
    del bytes  # unused
    return value


class MockPortHandler:
    def __init__(self, port):
        self.port = port
        # factory default baudrate
        self.baudrate = DEFAULT_BAUDRATE

    def openPort(self):  # noqa: N802
        return True

    def closePort(self):  # noqa: N802
        pass

    def setPacketTimeoutMillis(self, timeout_ms):  # noqa: N802
        del timeout_ms  # unused

    def getBaudRate(self):  # noqa: N802
        return self.baudrate

    def setBaudRate(self, baudrate):  # noqa: N802
        self.baudrate = baudrate


class MockPacketHandler:
    def __init__(self, protocol_version):
        del protocol_version  # unused
        # Use packet_handler.data to communicate across Read and Write
        self.data = {}


class MockGroupSyncRead:
    def __init__(self, port_handler, packet_handler, address, bytes):
        self.packet_handler = packet_handler

    def addParam(self, motor_index):  # noqa: N802
        if motor_index not in self.packet_handler.data:
            # Initialize motor default values
            self.packet_handler.data[motor_index] = {
                # Key (int) are from X_SERIES_CONTROL_TABLE
                7: motor_index,  # ID
                8: DEFAULT_BAUDRATE,  # Baud_rate
                10: 0,  # Drive_Mode
                64: 0,  # Torque_Enable
                132: 0,  # Present_Position
            }

    def txRxPacket(self):  # noqa: N802
        return COMM_SUCCESS

    def getData(self, index, address, bytes):  # noqa: N802
        return self.packet_handler.data[index][address]


class MockGroupSyncWrite:
    def __init__(self, port_handler, packet_handler, address, bytes):
        self.packet_handler = packet_handler
        self.address = address

    def addParam(self, index, data):  # noqa: N802
        self.changeParam(index, data)

    def txPacket(self):  # noqa: N802
        return COMM_SUCCESS

    def changeParam(self, index, data):  # noqa: N802
        self.packet_handler.data[index][self.address] = data
