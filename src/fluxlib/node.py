from abc import ABC, abstractmethod

import asyncio
import threading
import time
from dataclasses import dataclass
from logging import Logger
from typing import Dict, Any, Callable, TYPE_CHECKING, Optional
from asyncio import Task

from fluxlib.service import Service
from fluxlib.state import StateSlice

if TYPE_CHECKING:
    from fluxlib.service import Service

class NodeStatus:
    def stopped(self):
        return "stopped"

    def started(self):
        return "started"
    
    def created(self):
        return "created"

@dataclass
class DataInput:
    topics: list[str]
    alias: str

@dataclass
class DataOutput:
    alias: str
    topics: list[str]

@dataclass
class DataTimer:
    type: str
    interval: int

@dataclass
class DataNode:
    id: str
    type: str
    inputs: list[DataInput]
    outputs: list[DataOutput]
 
class Node:
    id: str
    state: Dict[str, Any]
    logger: Logger
    service: 'Service'
    outputs: Dict[str, object] = dict()
    inputs: Dict[str, object] = dict()
    input_tasks: list[Task]
    node: DataNode
    timer: DataTimer
    status_callback_on_stop: Callable[[], None]
    status_callback_on_start: Callable[[], None]
    status: str
    state: Dict[str, str]

    # add data like an object and also pass the settings
    def __init__(self,
                 service: 'Service',
                 node_id: str,
                 node: DataNode,
                 logger: Logger = None,
                 state: StateSlice = None,
                 timer: DataTimer = None,
                 on_tick: Optional[Callable[[], None]] = None,
                 status_factory: NodeStatus = NodeStatus()):
        self.timer = timer
        self.service = service
        self.id = node_id
        self.node = node
        self.state = state
        self.on_tick_callback = on_tick
        self.subscriptions = []

        if state == None:
            state = StateSlice(state=None, prefix=node_id)
        self.state = state

        for input in self.node.inputs:
            self.inputs[input.alias] = Input(input, self, service)
        
        for output in self.node.outputs:
            self.outputs[output.alias] = Output(output, self, service)
            
        if logger is not None:
            self.logger = logger
        else:
            self.logger = service.logger

        self.state = state
        self.status_factory = status_factory

    def set_status(self, status: str):
        self.status = status
        task = asyncio.create_task(self.on_state_changed())
        task.add_done_callback(lambda t: None)

    def input(self, alias: str):
        return self.inputs[alias]

    def output(self, alias: str) -> 'Output':
        return self.outputs[alias]

    def get_global_topic(self):
        return f"service/tick"
    
    async def init(self):
        await self.service.subscribe_handler(self.service.topic.node_settings(self.id), self.on_settings)
        await self.service.subscribe_handler(self.service.topic.node_status(self.id), self.on_status)

        for input in self.inputs.values():
            await input.listen()

        await self.set_status(self.status_factory.created())
            
    async def start(self) -> None:
        try:
            await self.on_start()
            self.set_status(self.status_factory.started())
        except Exception as err:
            await self.__on_error(err)
            return

        # async def read_input_queue(topic: str, queue: Queue):
        #     while True:
        #         msg = await queue.get()
        #         try:
        #             await self.on_input(topic, msg)
        #         except Exception as err:
        #             await self.__on_error(err)

        if not self.service.opts.hasGlobalTick and self.timer:
            self.tick_task = asyncio.create_task(self._tick_loop())
        elif self.service.opts.hasGlobalTick:
            if self.on_tick_callback not in self.subscriptions:
                self.service.subscribe(self.get_global_topic(), self.on_tick_callback)
        # for topic in self.input_topics:
        #     queue = await self.service.subscribe(topic)
        #     task = asyncio.create_task(read_input_queue(topic, queue))
        #     task.add_done_callback(lambda t: None)
        #     self.input_tasks.append(task)

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self.timer.interval / 1000)
            if self.on_tick_callback:
                await self.on_tick_callback()
 
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

    async def on_status(self, msg):
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

    async def on_input(self, msg: Any):
        pass

    async def on_settings(self, msg: Any):
        pass

    async def on_state_changed(self) -> None:
        await self.service.publish(self.service.topic.node_status(self.id), self.status)

    async def __on_error(self, err: Exception) -> None:
        self.logger.error(err)
        await self.on_error(err)
        await self.stop()


class NodeSync:
    id: str
    state: Dict[str, Any]
    logger: Logger
    service: 'Service'
    outputs: Dict[str, object]
    inputs: Dict[str, object]
    input_tasks: list[threading.Thread]
    node: DataNode
    timer: DataTimer
    status_callback_on_stop: Callable[[], None]
    status_callback_on_start: Callable[[], None]
    status: str
    state: Dict[str, str]

    def __init__(self,
                 service: 'Service',
                 node_id: str,
                 node: DataNode,
                 logger: Logger = None,
                 state: StateSlice = None,
                 timer: DataTimer = None,
                 on_tick: Optional[Callable[[], None]] = None,
                 status_factory: NodeStatus = NodeStatus()):
        self.timer = timer
        self.service = service
        self.id = node_id
        self.node = node
        self.on_tick_callback = on_tick
        self.subscriptions = []
        self.inputs = {}
        self.outputs = {}
        self.input_tasks = []

        if state == None:
            state = StateSlice(state=None, prefix=node_id)
        self.state = state

        for input in self.node.inputs:
            self.inputs[input.alias] = Input(input, node, service)

        for output in self.node.outputs:
            self.outputs[output.alias] = Output(output, node, service)

        if logger is not None:
            self.logger = logger
        else:
            self.logger = service.logger

        self.state = state
        self.status_factory = status_factory

    def set_status(self, status: str):
        self.status = status
        self.on_state_changed()

    def input(self, alias: str):
        return self.inputs[alias] or None

    def output(self, alias: str):
        return self.outputs[alias] or None

    def get_global_topic(self):
        return f"service/tick"

    def start(self) -> None:
        try:
            self.on_start()
            self.set_status(self.status_factory.started())
        except Exception as err:
            self.__on_error(err)
            return

        if not self.service.opts.hasGlobalTick and self.timer:
            self.tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
            self.tick_thread.start()
        elif self.service.opts.hasGlobalTick:
            if self.on_tick_callback not in self.subscriptions:
                self.service.subscribe(self.get_global_topic(), self.on_tick_callback)

    def _tick_loop(self) -> None:
        while True:
            time.sleep(self.timer.interval / 1000)
            if self.on_tick_callback:
                self.on_tick_callback()

    def stop(self) -> None:
        try:
            self.on_stop()
        except Exception as err:
            self.logger.error(err)
        finally:
            for task in self.input_tasks:
                task.join()  # Wait for input tasks to finish
            self.input_tasks.clear()

            for topic in self.input_topics:
                self.service.unsubscribe(topic)

            self.set_status(self.status_factory.stopped())

    def destroy(self) -> None:
        self.stop()
        self.on_destroy()

    def on_create(self) -> None:
        pass

    def on_start(self) -> None:
        pass

    def on_stop(self) -> None:
        pass

    def on_tick(self) -> None:
        if self.service.opts.hasGlobalTick:
            self.service.subscribe(self.get_global_topic())
            return

        if self.timer.interval:
            while True:
                time.sleep(self.timer.interval / 1000)

        return

    def on_destroy(self) -> None:
        pass

    def on_error(self, err: Exception) -> None:
        pass

    def on_input(self, topic: str, msg: Any):
        pass

    def on_state_changed(self) -> None:
        self.service.publish(self.service.topic.node_status(self.id), self.status)

    def __on_error(self, err: Exception) -> None:
        self.logger.error(err)
        self.on_error(err)
        self.stop()


class Input:
    topics: list[str]
    input: DataInput
    alias: str
    service: 'Service'
    node: Node
    state: StateSlice = StateSlice(state=None, prefix=None)

    def __init__(self, input: DataInput, node: DataNode, service):
        self.input: DataInput = input
        self.topics = input.topics
        self.service = service
        self.alias = input.alias
        self.node = node
        self.subscriptions = []

    async def listen(self):
        for topic in self.topics:
            print("input listen: ", topic)
            await self._subscribe(topic, self.store_value)

    def store_value(self, value):
        return self.state.set(self.alias, value)

    def read(self) -> str:
        return self.state.get(self.alias)

    async def _subscribe(self, topic, callback):
        return await self.service.subscribe_handler(topic, callback)
    
    async def subscribe_one(self, topic, callback):
        return await self.service.subscribe_handler(topic, callback)
    
    async def subscribe(self, callback):
        for topic in self.topics:
            await self._subscribe(topic, callback)

class Output:
    alias: str
    topics: list[str]
    service: 'Service'
    node: Node
    state: StateSlice = StateSlice(state=None, prefix=None)

    def __init__(self, output: DataOutput, node, service):
        self.topics = output.topics
        self.output: DataOutput = output
        self.alias = output.alias
        self.service = service
        self.node = node
    
    async def publish(self, data):
        for topic in self.topics:
            await self.service.publish(topic, data)
        return

    async def call(self, path, callback):
        return self.service.call(path, callback)