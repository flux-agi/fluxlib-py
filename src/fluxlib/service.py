from asyncio import Task
from dataclasses import dataclass
from logging import Logger, getLogger
from typing import Coroutine, Any, TypeVar, Generic, Callable, List, Dict, TYPE_CHECKING

import asyncio
import json
from types import SimpleNamespace

from asyncio.queues import Queue

from fluxmq.message import Message
from fluxmq.topic import Topic
from fluxmq.transport import Transport, SyncTransport
from fluxmq.status import Status

from fluxlib.state import StateSlice

Message = TypeVar('Message')

class TypedQueue(Queue, Generic[Message]):
    pass

if TYPE_CHECKING:
    from fluxlib.node import Node

@dataclass
class ServiceOptions:
    hasGlobalTick: bool

class Service:
    state: Dict[str, Any]
    transport: Transport
    topic: Topic
    status: Status
    opts: ServiceOptions
    id: str
    nodes: List['Node'] = []
    

    def __init__(self,
                 service_id: str = "UndefinedID",
                 logger: Logger = None,
                 state: StateSlice = StateSlice(state=None, prefix=None),
                 opts: ServiceOptions = None):
        self.id = service_id
        self.opts = opts
        self.state = state
        if logger is None:
            self.logger = getLogger()


        self.subscriptions = []

    def attach(self,
               transport: Transport,
               topic: Topic,
               status: Status) -> None:
        """
        attaches low level implementation of main abstractions
        :param transport:
        :param topic:
        :param status:
        :return:
        """

        self.transport = transport
        self.topic = topic
        self.status = status
        return

    async def run(self) -> None:
        await self.transport.connect()
        await self.subscribe_handler(self.topic.configuration(self.id), self.on_init)
        await self.subscribe_handler(self.topic.configuration(self.id), self.on_config)
        await self.subscribe_handler(self.topic.service_settings(self.id), self.on_settings)
        await self.subscribe_handler(self.topic.start(self.id), self.on_start)
        await self.subscribe_handler(self.topic.stop(self.id), self.on_stop)
        await self.subscribe_handler(self.topic.error(self.id), self.on_error)
        await self.subscribe_handler(self.topic.status(self.id), self.on_ready)
        await self.subscribe_handler(self.topic.restart_node(self.id), self.on_restart)

        await self.send_status(self.status.connected())
        await self.on_connected(self.id)

        return

    async def destroy_node_all(self) -> None:
        await self.destroy_node('*')

    async def start_node_all(self) -> None:
        await self.start_node('*')

    async def stop_node_all(self) -> None:
        await self.stop_node('*')

    async def destroy_node(self, node_id: str) -> None:
        for node in self.nodes:
            if node.node_id == node_id or node_id == '*':
                await node.destroy()
                self.nodes.remove(node)

    async def start_node(self, node_id: str) -> None:
        for node in self.nodes:
            if node.node_id == node_id or node_id == '*':
                await node.start()

    async def stop_node(self, node_id: str) -> None:
        for node in self.nodes:
            if node.node_id == node_id or node_id == '*':
                await node.stop()

    def append_node(self, node: 'Node') -> None:
        self.nodes.append(node)

    async def subscribe(self, topic: str) -> TypedQueue:
        if topic not in self.subscriptions:
            queue = await self.transport.subscribe(topic)
            return queue
        
        return

    async def subscribe_handler(self, topic, handler: Callable[[Message], Coroutine[Any, Any, None]]) -> Task:
        queue: Queue = await self.subscribe(topic)

        async def read_queue(queue: TypedQueue[Message]):
            while True:
                message = await queue.get()
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)

        task = asyncio.create_task(read_queue(queue))
        task.add_done_callback(lambda t: None)
        return task

    async def unsubscribe(self, topic: str):
        await self.transport.unsubscribe(topic)
        return

    async def publish(self, topic: str, message):
        await self.transport.publish(topic, message)
        return

    async def request(self, topic: str, payload):
        await self.transport.request(topic, payload)
        return

    async def respond(self, message: Message, response: bytes):
        await self.transport.respond(message, response)
        return

    async def send_status(self, status: str):
        topic = self.topic.status(self.id)
        await self.transport.publish(topic, status)

    async def send_node_state(self, node_id: str, status: str):
        topic = self.topic.set_node_state(node_id)
        await self.transport.publish(topic, status)

    async def on_init(self,  message: Message) -> None:
        data = json.loads(message.payload, object_hook=lambda d: SimpleNamespace(**d))
        self.config = data.payload.params
        await self.init()

    async def init(self) -> None:
        # config with list of nodes
        for node_data in self.config.nodes:
            node = await self.get_node(node_data)
            self.nodes.append(node)
        # initialize service store

    async def get_node(self, node_data: any) -> None:
        pass

    async def on_connected(self, message: Message) -> None:
        pass

    async def on_ready(self, message: Message) -> None:
        pass

    def ready(self, message: Message) -> None:
        pass

    async def on_start(self, message: Message) -> None:
        pass

    async def on_stop(self, message: Message) -> None:
        pass

    async def on_restart(self, message: Message) -> None:
        pass

    async def on_settings(self, message: Message) -> None:
        pass

    async def on_config(self, message: Message) -> None:
        pass

    async def on_tick(self, time: int) -> None:
        pass

    async def on_shutdown(self, signal_number, frame) -> None:
        pass

    async def on_error (self, message: Message) -> None:
        pass

class SyncService:
    state: Dict[str, Any]
    transport: SyncTransport
    topic: Topic
    status: Status
    opts: ServiceOptions
    id: str
    nodes: List['Node'] = []
    

    def __init__(self,
                 service_id: str = "UndefinedID",
                 logger: Logger = None,
                 state: StateSlice = StateSlice(state=None, prefix=None),
                 opts: ServiceOptions = None):
        self.id = service_id
        self.opts = opts
        self.state = state
        if logger is None:
            self.logger = getLogger()

        self.subscriptions = []

    def attach(self,
               transport: SyncTransport,
               topic: Topic,
               status: Status) -> None:
        """
        attaches low level implementation of main abstractions
        :param transport:
        :param topic:
        :param status:
        :return:
        """
        self.transport = transport
        self.topic = topic
        self.status = status
        return

    def run(self) -> None:
        self.transport.connect()

        self.subscribe_handler(self.topic.configuration(self.id), self.on_init)
        self.subscribe_handler(self.topic.configuration(self.id), self.on_config)
        self.subscribe_handler(self.topic.service_settings(self.id), self.on_settings)
        self.subscribe_handler(self.topic.start(self.id), self.on_start)
        self.subscribe_handler(self.topic.stop(self.id), self.on_stop)
        self.subscribe_handler(self.topic.error(self.id), self.on_error)
        self.subscribe_handler(self.topic.status(self.id), self.on_ready)
        self.subscribe_handler(self.topic.restart_node(self.id), self.on_restart)

        self.send_status(self.status.connected())
        self.on_connected(self.id)

        return

    def destroy_node_all(self) -> None:
        self.destroy_node('*')

    def start_node_all(self) -> None:
        self.start_node('*')

    def stop_node_all(self) -> None:
        self.stop_node('*')

    def destroy_node(self, node_id: str) -> None:
        for node in self.nodes:
            if node.node_id == node_id or node_id == '*':
                node.destroy()
                self.nodes.remove(node)

    def start_node(self, node_id: str) -> None:
        for node in self.nodes:
            if node.node_id == node_id or node_id == '*':
                node.start()

    def stop_node(self, node_id: str) -> None:
        for node in self.nodes:
            if node.node_id == node_id or node_id == '*':
                node.stop()

    def append_node(self, node: 'Node') -> None:
        self.nodes.append(node)

    def subscribe(self, topic: str, handler: Callable[[Message], None]):

        if handler is not None:
            if handler not in self.subscriptions:
                sub = self.transport.subscribe(topic, handler)
                self.subscriptions.append(handler)
                
                return sub
            
        return self.transport.subscribe(topic, None)
        

    def subscribe_handler(self, topic, handler: Callable[[Message], None]) -> None:
        self.subscribe(topic, handler)

    def unsubscribe(self, topic: str):
        self.transport.unsubscribe(topic)
        return

    def publish(self, topic: str, message):
        self.transport.publish(topic, message)
        return

    def request(self, topic: str, payload):
        self.transport.request(topic, payload)
        return

    def respond(self, message: Message, response: bytes):
        self.transport.respond(message, response)
        return

    def send_status(self, status: str):
        topic = self.topic.status(self.id)
        self.transport.publish(topic, status)

    def send_node_state(self, node_id: str, status: str):
        topic = self.topic.set_node_state(node_id)
        self.transport.publish(topic, status)

    def on_init(self,  message: Message) -> None:
        data = json.loads(message.payload, object_hook=lambda d: SimpleNamespace(**d))
        self.config = data.payload.params
        self.init()

    def init(self) -> None:
        # config with list of nodes
        for node_data in self.config.nodes:
            node = self.get_node(node_data)
            self.nodes.append(node)
        # initialize service store

    def get_node(self, node_data: any) -> None:
        pass

    def on_connected(self, message: Message) -> None:
        pass

    def on_ready(self, message: Message) -> None:
        pass

    def ready(self, message: Message) -> None:
        pass

    def call(self, path, callback: Callable[[], None]) -> None:
        pass

    def on_start(self, message: Message) -> None:
        pass

    def on_stop(self, message: Message) -> None:
        pass

    def on_restart(self, message: Message) -> None:
        pass

    def on_settings(self, message: Message) -> None:
        pass

    def on_config(self, message: Message) -> None:
        pass

    def on_tick(self, time: int) -> None:
        pass

    def on_shutdown(self, signal_number, frame) -> None:
        pass

    def on_error (self, message: Message) -> None:
        pass