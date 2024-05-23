import argparse
import asyncio
import logging
import websockets
import ssl
from datetime import datetime

from ocpp.routing import on
from ocpp.v16 import call, call_result
from ocpp.v16 import ChargePoint as cp
from ocpp.v16.enums import RegistrationStatus, ConfigurationStatus, RemoteStartStopStatus, ChargePointStatus

logging.basicConfig(level=logging.INFO)


class ChargePointSimlator(cp):
    is_charge_start = False
    is_charge_stop = False
    transaction_id = None
    id_tag = None
    meter_start = False
    energy = 0

    async def send_boot_notification(self):
        request = call.BootNotification(
            charge_point_model="KedaTest",
            charge_point_vendor="StarCharge",
            charge_point_serial_number="32523434233",
            firmware_version="2.3.6",
            iccid="255223422",
            imsi="342452322",
            meter_serial_number="4231435235",
            meter_type="AC"
        )
        response = await self.call(request)

        if response.status == RegistrationStatus.accepted:
            logging.info("%s: connected to central system", arguments["cp_id"])
            if response.interval:
                arguments["heartbeat_interval"] = response.interval
                logging.info(
                    "%s: heartbeat interval set to %s",
                    arguments["cp_id"],
                    response.interval
                )
                await asyncio.gather(
                    self.send_status_notification(0, ChargePointStatus.available),
                    self.send_status_notification(1, ChargePointStatus.available),
                    self.send_heartbeats(arguments),
                    self.core()
                )

        return True

    async def core(self):
        while True:
            if self.is_charge_start:
                await asyncio.gather(
                    self.send_start_transaction(),
                    self.send_status_notification(1, ChargePointStatus.charging)
                )
                self.is_charge_start = False

            if self.is_charge_stop:
                await asyncio.gather(
                    self.send_status_notification(1, ChargePointStatus.available),
                    self.send_stop_transaction()
                )
                self.is_charge_stop = False

            await asyncio.sleep(1)

    async def send_heartbeats(self, arguments):
        while True:
            request = call.Heartbeat()
            await self.call(request)
            await asyncio.sleep(arguments["heartbeat_interval"])

    @on('ChangeConfiguration')
    async def on_change_configuration(self, key, value):
        """
        处理 ChangeConfiguration 请求。
        """
        # 在这里添加你的逻辑来处理配置更改。
        # 例如，检查 key 是否有效，尝试更改配置，等等。
        # 假设我们总是接受配置更改请求：
        print(key)
        print(value)

        # 返回一个 ChangeConfiguration.conf 消息，指示请求被接受。
        return call_result.ChangeConfiguration(
            status=ConfigurationStatus.accepted
        )

    @on('RemoteStartTransaction')
    async def on_remote_start_transaction(self, id_tag, connector_id):
        """
        处理 RemoteStartTransaction 请求。
        """
        # 在这里添加你的逻辑来处理配置更改。
        # 例如，检查 key 是否有效，尝试更改配置，等等。
        # 假设我们总是接受配置更改请求：
        self.id_tag = id_tag
        self.is_charge_start = True

        # 返回一个 ChangeConfiguration.conf 消息，指示请求被接受。
        return call_result.RemoteStartTransaction(
            status=RemoteStartStopStatus.accepted
        )

    @on('RemoteStopTransaction')
    async def on_remote_stop_transaction(self, transaction_id):
        """
        处理 RemoteStopTransaction 请求。
        """
        # 在这里添加你的逻辑来处理配置更改。
        # 例如，检查 key 是否有效，尝试更改配置，等等。
        # 假设我们总是接受配置更改请求：
        print(transaction_id)

        self.meter_start = False
        self.is_charge_stop = True

        # 返回一个 ChangeConfiguration.conf 消息，指示请求被接受。
        return call_result.RemoteStopTransaction(
            status=RemoteStartStopStatus.accepted
        )

    async def send_status_notification(self, connector_id, status):
        """
        发送 StatusNotification 消息到中央系统。
        """
        request = call.StatusNotification(
            connector_id=connector_id,
            status=status,
            error_code='NoError'
        )
        response = await self.call(request)
        return response

    async def send_start_transaction(self):
        """
        发送 StartTransaction 消息到中央系统。
        """
        request = call.StartTransaction(
            connector_id=1,
            id_tag=self.id_tag,
            meter_start=self.energy,
            timestamp=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        )
        response = await self.call(request)
        self.transaction_id = response.transaction_id
        self.meter_start = True
        await self.send_meter_values()
        return response

    async def send_stop_transaction(self):
        """
        发送 StopTransaction 消息到中央系统。
        """
        request = call.StopTransaction(
            transaction_id=self.transaction_id,
            id_tag=self.id_tag,
            meter_stop=self.energy,
            timestamp=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            reason="Remote"
        )
        response = await self.call(request)
        return response

    async def send_meter_values(self):
        while self.meter_start:
            request = call.MeterValues(
                connector_id=1,
                transaction_id=self.transaction_id,
                meter_value=[
                    {
                        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
                        "sampledValue": [
                            {
                                "value": "234.1",
                                "context": "Transaction.Begin",
                                "measurand": "Voltage",
                                "location": "Outlet",
                                "unit": "V",
                                "phase": "L1"
                            },
                            # {
                            #     "value": "235.5",
                            #     "context": "Transaction.Begin",
                            #     "measurand": "Voltage",
                            #     "location": "Outlet",
                            #     "unit": "V",
                            #     "phase": "L2"
                            # },
                            # {
                            #     "value": "234.6",
                            #     "context": "Transaction.Begin",
                            #     "measurand": "Voltage",
                            #     "location": "Outlet",
                            #     "unit": "V",
                            #     "phase": "L3"
                            # },
                            {
                                "value": "3.00",
                                "context": "Transaction.Begin",
                                "measurand": "Current.Import",
                                "location": "Outlet",
                                "unit": "A",
                                "phase": "L1"
                            },
                            # {
                            #     "value": "4.00",
                            #     "context": "Transaction.Begin",
                            #     "measurand": "Current.Import",
                            #     "location": "Outlet",
                            #     "unit": "A",
                            #     "phase": "L2"
                            # },
                            # {
                            #     "value": "5.00",
                            #     "context": "Transaction.Begin",
                            #     "measurand": "Current.Import",
                            #     "location": "Outlet",
                            #     "unit": "A",
                            #     "phase": "L3"
                            # },
                            {
                                "value": "10000",
                                "context": "Transaction.Begin",
                                "measurand": "Power.Active.Import",
                                "location": "Outlet",
                                "unit": "W"
                            },
                            {
                                "value": str(self.energy),
                                "context": "Transaction.Begin",
                                "measurand": "Energy.Active.Import.Register",
                                "location": "Outlet",
                                "unit": "Wh"
                            }
                        ]
                    }
                ]
            )
            self.energy += 10
            await self.call(request)
            await asyncio.sleep(60)


async def main(arguments):
    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.load_verify_locations('/src/AmazonRootCA1.pem')

        async with websockets.connect(
                f"{arguments['url']}/{arguments['cp_id']}",
                subprotocols=["ocpp1.6"],
                ssl=ssl_context
        ) as ws:
            cp = ChargePointSimlator(arguments["cp_id"], ws)
            await asyncio.gather(cp.start(), cp.send_boot_notification())
    except Exception as e:
        logging.error("%s: %s", arguments["cp_id"], e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="The NLB URL",
                        default="wss://test.execute-api.ap-south-1.amazonaws.com/test/?deviceId",
                        required=False)
    parser.add_argument(
        "--cp-id", help="The Charge Point ID", default="cp_test", required=False
    )
    parser.add_argument(
        "--cp-model",
        help="The Change Point model",
        default="CHARGE_POINT_MODEL",
        required=False,
    )
    parser.add_argument(
        "--cp-vendor",
        help="The Change Point vendor name",
        default="CHARGE_POINT_VENDOR",
        required=False,
    )
    parser.add_argument(
        "--cp-version",
        help="The Change Point firmware version",
        default="1.2.3.4",
        required=False,
    )
    parser.add_argument(
        "--cp-serial",
        help="The Change Point serial number",
        default="CP1234567890A01",
        required=False,
    )

    arguments = vars(parser.parse_args())
    asyncio.run(main(arguments))
