from abc import ABC, abstractmethod

import asyncio
from dataclasses import dataclass
from logging import Logger
from typing import Dict, Any, Callable, TYPE_CHECKING
from asyncio import Task
from asyncio import Queue

from fluxlib.service import Service
from fluxlib.state import StateSlice

if TYPE_CHECKING:
    from fluxlib.service import Service

port_key = "some_key"

class NodeStatus:
    def stopped(self):
        return "stopped"

    def started(self):
        return "started"

@dataclass
class DataPort:
    topic: str
    alias: str
    direction: str

@dataclass
class DataTimer:
    type: str
    interval: int

@dataclass
class DataNode:
    id: str
    ports: list[DataPort]

class Port:
    topic: str
    port: DataPort
    service: 'Service'
    node: DataNode
    state: StateSlice = StateSlice()

    def __init__(self, port: DataPort, node, service):
        self.topic = f"{node.id}/{port_key}"
        self.port: DataPort = port
        self.service = service
        self.node = node
        self.subscriptions = []
        
        self.listen(port)

    def listen(self, port: DataPort):
        if port.direction == "TARGET":
            self.subscribe(self.topic, self.store_value)

    def store_value(self, value):
        return self.state.set(self.port.alias, value)

    def read(self) -> str:
        return self.node.state.get(self.port.alias)
    
    def subscribe(self, callback):
        if callback not in self.subscriptions:
            self._subscribe(self.topic, callback)
        return

    def _subscribe(self, callback):
        self.subscriptions.append(callback)
        self.service.subscribe(self.topic, callback)
        return
    
    def publish(self, data):
        return self.service.publish(self.topic, data)

    def call(self, path, callback):
        return self.service.call(path, callback)
    
class Node:
    id: str
    state: Dict[str, Any]
    logger: Logger
    service: 'Service'
    outputs: Dict[str, object]
    inputs: Dict[str, object]
    input_tasks: list[Task]
    node_id: str
    node: DataNode
    timer: DataTimer
    status_callback_on_stop: Callable[[], None]
    status_callback_on_start: Callable[[], None]
    status: str
    state: Dict[str, str]
    ports: list[DataPort]

    # add data like an object and also pass the settings
    def __init__(self,
                 service: 'Service',
                 node_id: str,
                 node: DataNode,
                 logger: Logger = None,
                 state: StateSlice = StateSlice(),
                 timer: DataTimer = None,
                 status_factory: NodeStatus = NodeStatus()):
        self.timer = timer
        self.service = service
        self.node_id = node_id
        self.node = node
        self.state = state

        for port in filter(lambda p: p.direction == "SOURCE", self.node.ports):
            self.inputs[port.alias] = Port(port, node, service)
        
        for port in filter(lambda p: p.direction == "TARGET", self.node.ports):
            self.outputs[port.alias] = Port(port, node, service)

        if logger is not None:
            self.logger = logger
        else:
            self.logger = service.logger

        self.state = state
        self.status_factory = status_factory
        asyncio.run(self.on_create())

    def set_status(self, status: str):
        self.status = status
        task = asyncio.create_task(self.on_state_changed())
        task.add_done_callback(lambda t: None)

    def input(self, alias: str):
        return self.ports[alias]

    def output(self, alias: str):
        return self.ports[alias]

    def get_global_topic(self):
        return f"service/tick"
    
    async def start(self) -> None:
        try:
            await self.on_start()
            self.set_status(self.status_factory.started())
        except Exception as err:
            await self.__on_error(err)
            return

        async def read_input_queue(topic: str, queue: Queue):
            while True:
                msg = await queue.get()
                try:
                    await self.on_input(topic, msg)
                except Exception as err:
                    await self.__on_error(err)

        for topic in self.input_topics:
            queue = await self.service.subscribe(topic)
            task = asyncio.create_task(read_input_queue(topic, queue))
            task.add_done_callback(lambda t: None)
            self.input_tasks.append(task)

    async def stop(self) -> None:
        try:
            await self.on_stop()
        except Exception as err:
            self.logger.error(err)
        finally:
            for task in self.input_tasks:
                task.cancel()
            self.input_tasks.clear()

            for topic in self.input_topics:
                await self.service.unsubscribe(topic)

            self.set_status(self.status_factory.stopped())

    async def destroy(self) -> None:
        await self.stop()
        await self.on_destroy()

    async def on_create(self) -> None:
        pass

    async def on_start(self) -> None:
        pass

    async def on_stop(self) -> None:
        pass

    async def on_tick(self) -> None:
        if self.service.opts.hasGlobalTick:
            self.service.subscribe(self.get_global_topic())
            return
        
        if self.timer.interval:
            while True:
                await asyncio.sleep(self.timer.interval / 1000)

        return

    async def on_destroy(self) -> None:
        pass

    async def on_error(self, err: Exception) -> None:
        pass

    async def on_input(self, topic: str, msg: Any):
        pass

    async def on_state_changed(self) -> None:
        await self.service.publish(self.service.topic.set_node_status(self.node_id), self.status)

    async def __on_error(self, err: Exception) -> None:
        self.logger.error(err)
        await self.on_error(err)
        await self.stop()

class NodeFactory(ABC):
    @abstractmethod
    def create_node(self, service: 'Service') -> Node:
        pass
