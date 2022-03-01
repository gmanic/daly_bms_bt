import asyncio
import subprocess
import logging
from bleak import BleakClient
from .daly_bms import DalyBMS
from .logger import Logger


class DalyBMSBluetooth(DalyBMS):
    def __init__(self, mac_address, logger=None, adapter="hci0", request_retries=3):
        """

        :param request_retries: How often read requests should get repeated in case that they fail (Default: 3).
        :param logger: Python Logger object for output (Default: None)
        """
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
        DalyBMS.__init__(self, request_retries=request_retries, address=8, logger=logger)
        self.client = None
        self.response_cache = {}
        self.mac_address = mac_address
        self.logger.info("Set up Bleak client, adapter %s" % adapter) 
        self.client = BleakClient(self.mac_address, device=adapter, timeout=15)

    async def connect(self):
        """
        Open the connection to the Bluetooth device.

        :param mac_address: MAC address of the Bluetooth device
        """
        try:
            """
            When an earlier execution of the script crashed, the connection to the devices stays open and future 
            connection attempts would fail with this error:
            bleak.exc.BleakError: Device with address AA:BB:CC:DD:EE:FF was not found.
            see https://github.com/hbldh/bleak/issues/367
            """
            open_blue = subprocess.Popen(["bluetoothctl"], shell=True, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
            open_blue.communicate(b"disconnect %s\n" % self.mac_address.encode('utf-8'))
            open_blue.kill()
        except:
            pass
        self.logger.info("Bluetooth connecting...")
        try:
            await self.client.connect()
        except:
            self.logger.debug("Bluetooth connection failed")
            return False
        self.logger.info("Bluetooth connected")
        await self.client.start_notify(17, self._notification_callback)
        await self.client.write_gatt_char(48, bytearray(b""))

    async def disconnect(self):
        """
        Disconnect from the Bluetooth device
        """
        self.logger.info("Bluetooth Disconnecting")
        await self.client.disconnect()
        self.logger.info("Bluetooth Disconnected")

    async def _read_request(self, command, max_responses=1):
        response_data = None
        x = None
        for x in range(0, self.request_retries):
            response_data = await self._read(
                command=command,
                max_responses=max_responses)
            if not response_data:
                self.logger.debug("%x. try failed, retrying..." % (x + 1))
                await asyncio.sleep(0.2)
            else:
                break
        if not response_data:
            self.logger.error('%s failed after %s tries' % (command, x + 1))
            return False
        return response_data

    async def _read(self, command, max_responses=1):
        self.logger.debug("-- %s ------------------------" % command)
        self.response_cache[command] = {"queue": [],
                                        "future": asyncio.Future(),
                                        "max_responses": max_responses,
                                        "done": False}

        message_bytes = self._format_message(command)
        result = await self._async_char_write(command, message_bytes)
        self.logger.debug("got %s" % result)
        if not result:
            return False
        if max_responses == 1:
            return result[0]
        else:
            return result

    def _notification_callback(self, handle, data):
        self.logger.debug("handle %s, data %s, len %s" % (handle, repr(data), len(data)))
        responses = []
        if len(data) == 13:
            if int.from_bytes(self._calc_crc(data[:12]), 'little') != data[12]:
                self.logger.info("Return from BMS: CRC wrong")
                return
            responses.append(data)
        elif len(data) == 26:
            if (int.from_bytes(self._calc_crc(data[:12]), 'little') != data[12]) or (int.from_bytes(self._calc_crc(data[13:25]), 'little') != data[25]):
                self.logger.info("Return from BMS: CRC wrong")
                return
            responses.append(data[:13])
            responses.append(data[13:])
        else:
            self.logger.info("did not receive 13 or 26 bytes, not implemented bytes: %i" % len(data))
        for response_bytes in responses:
            command = response_bytes[2:3].hex()
            if self.response_cache[command]["done"] is True:
                self.logger.info("skipping response for %s, done - received more data than expected" % command)
                return
            self.response_cache[command]["queue"].append(response_bytes[4:-1])
            if len(self.response_cache[command]["queue"]) == self.response_cache[command]["max_responses"]:
                self.response_cache[command]["done"] = True
                self.response_cache[command]["future"].set_result(self.response_cache[command]["queue"])

    async def _async_char_write(self, command, value):
        if not self.client.is_connected:
            self.logger.info("Connecting...")
            await self.client.connect()

        await self.client.write_gatt_char(15, value)
        self.logger.debug("Waiting...")
        try:
            result = await asyncio.wait_for(self.response_cache[command]["future"], 5)
        except asyncio.TimeoutError:
            self.logger.warning("Timeout while waiting for %s response" % command)
            return False
        self.logger.debug("got %s" % result)
        return result

    # wrap all sync functions so that they can be awaited
    async def get_soc(self):
        response_data = await self._read_request("90")
        return super().get_soc(response_data=response_data)

    async def get_cell_voltage_range(self):
        response_data = await self._read_request("91")
        return super().get_cell_voltage_range(response_data=response_data)


    async def get_alarm_voltages(self, pack_cell=None):
        if pack_cell == "Cell":
            cmd = "59"
        elif pack_cell == "Pack":
            cmd = "5a"
        else:
            self.logger.error("Wrong Call to alarm_voltages, missing Pack or Cell")
        response_data = await self._read_request(cmd)
        return super().get_alarm_voltages(response_data=response_data, pack_cell=pack_cell)

    async def get_temperature_range(self):
        response_data = await self._read_request("92")
        return super().get_temperature_range(response_data=response_data)

    async def get_hw_sw_version(self, hard_soft):
        if hard_soft == "Hardware":
            cmd="63"
        elif hard_soft == "Software":
            cmd="62"
        else:
            self.logger.error("No Hard/Software selected for version query")
        response_data = await self._read_request(cmd, max_responses=2)
        return super().get_hw_sw_version(response_data=response_data, hard_soft=hard_soft)

    async def get_mosfet_status(self):
        response_data = await self._read_request("93")
        return super().get_mosfet_status(response_data=response_data)

    async def get_status(self):
        response_data = await self._read_request("94")
        return super().get_status(response_data=response_data)

    async def get_cell_voltages(self):
        if not self.status:
            await self.get_status()
        max_responses = self._calc_num_responses('cells', 3)
        if not max_responses:
            return
        response_data = await self._read_request("95", max_responses=max_responses)
        return super().get_cell_voltages(response_data=response_data)

    async def get_temperatures(self):
        if not self.status:
            await self.get_status()
        max_responses = self._calc_num_responses('temperature_sensors', 7)
        response_data = await self._read_request("96", max_responses=max_responses)
        return super().get_temperatures(response_data=response_data)

    async def get_balancing_status(self):
        response_data = await self._read_request("97")
        return super().get_balancing_status(response_data=response_data)

    async def get_alarms_diff_temp_volt(self):
        response_data = await self._read_request("5e")
        return super().get_alarms_diff_temp_volt(response_data=response_data)

    async def get_alarms_load_charge(self):
        response_data = await self._read_request("5b")
        return super().get_alarms_load_charge(response_data=response_data)

    async def get_rated_nominals(self):
        response_data = await self._read_request("50")
        return super().get_rated_nominals(response_data=response_data)

    async def get_balance_settings(self):
        response_data = await self._read_request("5f")
        return super().get_balance_settings(response_data=response_data)

    async def get_short_shutdownamp_ohm(self):
        response_data = await self._read_request("60")
        return super().get_short_shutdownamp_ohm(response_data=response_data)

    async def get_errors(self):
        response_data = await self._read_request("98")
        return super().get_errors(response_data=response_data)
