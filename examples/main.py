import asyncio
import json

from typing import Any
from logging import getLogger

from fluxmq.adapter.nats import Nats, NatsTopic, NatsStatus
from fluxmq.message import Message

from fluxlib.service import Service
from fluxlib.node import Node


class Runtime:
    """
    some runtime implementation
    """

    def start(self):
        pass

    def stop(self):
        pass


class RuntimeNode(Node):
    runtime: Any

    async def on_create(self) -> None:
        self.runtime = Runtime()

    async def on_start(self) -> None:
        self.logger.debug(f"Node started.")
        """
        should start Runtime engine here
        """
        self.runtime.start()
        return

    async def on_stop(self) -> None:
        self.logger.debug(f"Node stopped.")
        """
        should stop Runtime engine here
        """
        self.runtime.stop()
        return


class RuntimeService(Service):
    async def on_init(self, message: Message) -> None:
        config = json.loads(message.payload.encode())

        node = RuntimeNode(service=self,
                           node_id=config['node_id'],
                           output_topics=config['output_topics'],
                           input_topics=config['input_topics'])
        self.append_node(node)

    async def on_settings(self, message: Message) -> None:
        config = json.loads(message.payload.encode())

        node = Node(service=self,
                           node_id=config['node_id'],
                           output_topics=config['output_topics'],
                           input_topics=config['input_topics'])
        self.append_node(node)

    async def on_start(self, message: Message) -> None:
        await self.start_node_all()

    async def on_connected(self, message: Message):
        print("connected: ", message)

    async def on_stop(self, message: Message) -> None:
        await self.stop_node_all()


    async def on_error(self, message: Message):
        print("asdasdasd")

    async def on_control(self, message: Message):
        data = json.loads(message.payload.encode())
        if data['command'] == "set":
            self.logger.debug(f"Executing set command.")
        return

    async def on_shutdown(self, signal_number, frame):
        self.logger.debug(f"Shutting down service.")
        pass

    async def on_tick(self, time: int):
        self.logger.debug(f"System coordinated time: {time}")
        pass


async def main():
    service = RuntimeService(logger=getLogger("main"),
                             service_id="test")
    service.attach(transport=Nats(['nats://127.0.0.1:4222']),
                   status=NatsStatus(),
                   topic=NatsTopic())

    await service.run()

    while True:
        await asyncio.sleep(1)

asyncio.run(main())

# TEMP_PORT = "temp"

# class AbstractNode(Node):
#     def on_ready(self):
#         pin = self.settings.pin
#         self.state.set("pin", pin ** 2)
#         self.input("humidity").subscribe(lambda h: print(h))

#     def on_tick(self, time, opts):
#         pin = self.state.get("pin")
#         humidity = self.input("humidity").read() # read last value
#         if humidity:
#             print(f"")
#         temp = 33 # get some temperature
#         self.output(TEMP_PORT).publish(temp)

# class AbstractService(Service):
#     def on_ready(self, message: Service) -> None:
#         print("ready")
    
#     def get_node(self, node: Node) -> None:
#         return AbstractNode(node)


# # main.py
# service = AbstractService(os.get_env().settings)

# service.run(flux_mq)