import argparse
import bluepy.btle
from bluepy.btle import UUID, Peripheral, DefaultDelegate, DBG, Descriptor, Characteristic

_UART_SERVICE_UUID = UUID('6e400001-b5a3-f393-e0a9-e50e24dcca9e')
_UART_TX_UUID = UUID('6e400002-b5a3-f393-e0a9-e50e24dcca9e')
_UART_RX_UUID = UUID('6e400003-b5a3-f393-e0a9-e50e24dcca9e')
_ENABLE_NOTIFICATIONS_DESC_UUID = UUID('00002902-0000-1000-8000-00805f9b34fb')


class UARTServer(Peripheral):
    def __init__(self, addr, is_random=False):
        addrType = 'random' if is_random else 'public'
        Peripheral.__init__(self, addr, addrType=addrType)

        self._uart_delegate = UARTServerDelegate()
        self.setDelegate(self._uart_delegate)

        self._service = self.getServiceByUUID(_UART_SERVICE_UUID)
        if not self._service:
            raise RuntimeError('The provided host does not have the UART service')

        self._tx_char = self._service.getCharacteristics('6e400002-b5a3-f393-e0a9-e50e24dcca9e')[0]  # type: Characteristic
        self._rx_char = self._service.getCharacteristics('6e400003-b5a3-f393-e0a9-e50e24dcca9e')[0]  # type: Characteristic
        self._notify_descriptor = self._enable_rx_notifications()  # type: Descriptor

    def _enable_rx_notifications(self):
        DBG('Trying to find rx enable descriptor')
        notify_descriptors = self._rx_char.getDescriptors(forUUID=_ENABLE_NOTIFICATIONS_DESC_UUID)
        if not notify_descriptors:
            raise RuntimeError('Failed to find descriptor for enabling notifications')

        notify_descriptor = notify_descriptors[0]  # type: Descriptor
        notify_descriptor.write(bytearray([0x01, 0x00]))
        return notify_descriptor

    def write_string(self, s):
        string_bytes = s.encode('UTF-8')
        self._tx_char.write(string_bytes)

    def read_string(self, timeout=1.0):
        self.waitForNotifications(timeout=timeout)
        items = self._uart_delegate.get_items(self._rx_char.valHandle)
        if not items:
            return None

        ret = ''
        for item in items:
            item_utf8 = item.decode('UTF-8')
            ret += item_utf8
        return ret


class UARTServerDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)
        self._incoming_notifications = {}

    def handleNotification(self, hnd, data):
        DefaultDelegate.handleNotification(self, hnd, data)
        DBG('in handle notification: %s %s' % (hnd, data))
        if hnd not in self._incoming_notifications:
            self._incoming_notifications[hnd] = []
        self._incoming_notifications[hnd].append(data)

    def get_items(self, handle):
        DBG('get_items called with handle: %s' % handle)
        if handle not in self._incoming_notifications:
            return None
        return self._incoming_notifications[handle]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('host', action='store', help='MAC of BT device')
    parser.add_argument('string_to_send', help='string to send over UART')
    parser.add_argument('--random', action='store_true', help="use the random type of device connection")
    parser.add_argument('--debug', action='store_true', help="enable bluepy debugging")
    parser.add_argument('--timeout', default=1.0, help="timeout when waiting for response")
    args = parser.parse_args()

    if args.debug:
        print('Enabling bluepy debugging')
        bluepy.btle.Debugging = True

    print('Connecting to ' + args.host)
    uart_server = UARTServer(args.host, is_random=args.random)

    uart_server.write_string(args.string_to_send)

    response = uart_server.read_string(timeout=args.timeout)
    if response is None:
        print('Failed to get a response within %f second' % args.timeout)
    else:
        print('Got response: %s' % response)

    uart_server.disconnect()
    del uart_server

if __name__ == "__main__":
    main()
