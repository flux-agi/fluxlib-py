from abc import ABC, abstractmethod

import asyncio
import threading
import time
import traceback
from dataclasses import dataclass, field
from logging import Logger, getLogger
from typing import List, Dict, Any, Callable, TYPE_CHECKING, Optional, Union, TypeVar, Generic

from fluxlib.service import Service
from fluxlib.state import StateSlice

if TYPE_CHECKING:
    from fluxlib.service import Service

class NodeStatus:
    """
    Provides standard status values for nodes.
    """
    def stopped(self) -> str:
        """Status value for a stopped node."""
        return "stopped"

    def started(self) -> str:
        """Status value for a started node."""
        return "started"
    
    def created(self) -> str:
        """Status value for a newly created node."""
        return "created"

@dataclass
class DataInput:
    """
    Configuration for a node input.
    
    Attributes:
        topics: List of topics to subscribe to
        alias: Name to reference this input by
    """
    topics: List[str]
    alias: str

@dataclass
class DataOutput:
    """
    Configuration for a node output.
    
    Attributes:
        alias: Name to reference this output by
        topics: List of topics to publish to
    """
    alias: str
    topics: List[str]

@dataclass
class DataTimer:
    """
    Configuration for a node timer.
    
    Attributes:
        type: Type of timer (e.g., 'interval')
        interval: Time between ticks in milliseconds
    """
    type: str
    interval: int

@dataclass
class DataNode:
    """
    Configuration for a node.
    
    Attributes:
        id: Unique identifier for the node
        type: Type of node
        settings: Configuration settings
        inputs: List of input configurations
        outputs: List of output configurations
    """
    id: str
    type: str
    settings: Dict[str, Any] = field(default_factory=dict)
    inputs: List[DataInput] = field(default_factory=list)
    outputs: List[DataOutput] = field(default_factory=list)
 
class Node:
    """
    Base class for nodes in the Flux system.
    
    A node is a processing unit that can receive inputs, process them,
    and produce outputs. Nodes are managed by a Service.
    """
    id: str
    state: Dict[str, Any]
    logger: Logger
    service: 'Service'
    outputs: Dict[str, 'Output'] = field(default_factory=dict)
    inputs: Dict[str, 'Input'] = field(default_factory=dict)
    input_tasks: List[asyncio.Task]
    node: DataNode
    timer: Optional[DataTimer]
    status_callback_on_stop: Optional[Callable[[], None]]
    status_callback_on_start: Optional[Callable[[], None]]
    status: str
    settings: Dict[str, Any] = field(default_factory=dict)
    _tick_task: Optional[asyncio.Task] = None

    def __init__(self,
                 service: 'Service',
                 node_id: str,
                 node: DataNode,
                 logger: Optional[Logger] = None,
                 state: Optional[StateSlice] = None,
                 timer: Optional[DataTimer] = None,
                 on_tick: Optional[Callable[[], None]] = None,
                 status_factory: Optional[NodeStatus] = None):
        """
        Initialize a new Node.
        
        Args:
            service: The service managing this node
            node_id: Unique identifier for this node
            node: Configuration for this node
            logger: Logger for node logs
            state: StateSlice for node state
            timer: Timer configuration
            on_tick: Callback for timer ticks
            status_factory: Factory for status values
        """
        self.id = node_id
        self.service = service
        self.node = node
        self.timer = timer
        self.input_tasks = []
        
        # Set up logger
        if logger is None:
            self.logger = getLogger(f"node.{node_id}")
        else:
            self.logger = logger
            
        # Set up state
        if state is None:
            self.state = StateSlice(state=None, prefix=f"node/{node_id}")
        else:
            self.state = state
            
        # Set up status factory
        if status_factory is None:
            self.status_factory = NodeStatus()
        else:
            self.status_factory = status_factory
            
        # Initialize status
        self.status = self.status_factory.created()
        
        # Initialize settings from node configuration
        if hasattr(node, 'settings') and node.settings:
            self.settings = node.settings.copy()
        else:
            self.settings = {}
            
        # Set up inputs
        if hasattr(node, 'inputs') and node.inputs:
            for input_data in node.inputs:
                input_obj = Input(input_data, node, service)
                self.inputs[input_obj.alias] = input_obj
                
        # Set up outputs
        if hasattr(node, 'outputs') and node.outputs:
            for output_data in node.outputs:
                output_obj = Output(output_data, node, service)
                self.outputs[output_obj.alias] = output_obj
                
        self.logger.info(f"Node {node_id} initialized")

    def set_status(self, status: str) -> None:
        """
        Update the node's status.
        
        Args:
            status: The new status value
        """
        self.status = status
        self.logger.debug(f"Node {self.id} status set to {status}")

    def input(self, alias: str) -> 'Input':
        """
        Get an input by alias.
        
        Args:
            alias: The alias of the input
            
        Returns:
            The input object
        """
        if alias not in self.inputs:
            self.logger.warning(f"Input '{alias}' not found in node {self.id}")
            raise KeyError(f"Input '{alias}' not found")
        return self.inputs[alias]

    def output(self, alias: str) -> 'Output':
        """
        Get an output by alias.
        
        Args:
            alias: The alias of the output
            
        Returns:
            The output object
        """
        if alias not in self.outputs:
            self.logger.warning(f"Output '{alias}' not found in node {self.id}")
            raise KeyError(f"Output '{alias}' not found")
        return self.outputs[alias]

    def get_global_topic(self) -> str:
        """
        Get the global topic for this node.
        
        Returns:
            The global topic string
        """
        return f"node/{self.id}"

    async def init(self) -> None:
        """
        Initialize the node.
        
        This method sets up the node's inputs and outputs and
        calls the on_create hook.
        """
        try:
            self.logger.info(f"Initializing node {self.id}")
            
            # Call the on_create hook
            await self.on_create()
            
            # Set the initial status
            self.set_status(self.status_factory.created())
            
            # Notify the service of the node's status
            await self.service.send_node_state(self.id, self.status)
            
            self.logger.info(f"Node {self.id} initialized")
        except Exception as e:
            self.logger.error(f"Error initializing node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def start(self) -> None:
        """
        Start the node.
        
        This method starts the node's inputs and timer and
        calls the on_start hook.
        """
        try:
            self.logger.info(f"Starting node {self.id}")
            
            # Start all inputs
            for alias, input_obj in self.inputs.items():
                try:
                    task = asyncio.create_task(input_obj.listen())
                    self.input_tasks.append(task)
                    self.logger.debug(f"Started input {alias} for node {self.id}")
                except Exception as e:
                    self.logger.error(f"Error starting input {alias} for node {self.id}: {str(e)}")
                    self.logger.debug(f"Exception details: {traceback.format_exc()}")
            
            # Start the timer if configured
            if self.timer:
                self._tick_task = asyncio.create_task(self._tick_loop())
                self.logger.debug(f"Started timer for node {self.id}")
            
            # Call the on_start hook
            await self.on_start()
            
            # Set the status to started
            self.set_status(self.status_factory.started())
            
            # Notify the service of the node's status
            await self.service.send_node_state(self.id, self.status)
            
            # Call the status callback if provided
            if self.status_callback_on_start:
                self.status_callback_on_start()
                
            self.logger.info(f"Node {self.id} started")
        except Exception as e:
            self.logger.error(f"Error starting node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def _tick_loop(self) -> None:
        """
        Run the timer tick loop.
        
        This method runs a loop that calls the on_tick hook
        at the configured interval.
        """
        if not self.timer:
            return
            
        try:
            while True:
                await self.on_tick()
                await asyncio.sleep(self.timer.interval / 1000.0)  # Convert ms to seconds
        except asyncio.CancelledError:
            self.logger.debug(f"Tick loop for node {self.id} cancelled")
        except Exception as e:
            self.logger.error(f"Error in tick loop for node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def stop(self) -> None:
        """
        Stop the node.
        
        This method stops the node's inputs and timer and
        calls the on_stop hook.
        """
        try:
            self.logger.info(f"Stopping node {self.id}")
            
            # Cancel all input tasks
            for task in self.input_tasks:
                task.cancel()
                
            # Clear the input tasks list
            self.input_tasks = []
            
            # Cancel the tick task if running
            if self._tick_task:
                self._tick_task.cancel()
                self._tick_task = None
            
            # Call the on_stop hook
            await self.on_stop()
            
            # Set the status to stopped
            self.set_status(self.status_factory.stopped())
            
            # Notify the service of the node's status
            await self.service.send_node_state(self.id, self.status)
            
            # Call the status callback if provided
            if self.status_callback_on_stop:
                self.status_callback_on_stop()
                
            self.logger.info(f"Node {self.id} stopped")
        except Exception as e:
            self.logger.error(f"Error stopping node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def destroy(self) -> None:
        """
        Destroy the node.
        
        This method stops the node and calls the on_destroy hook.
        """
        try:
            self.logger.info(f"Destroying node {self.id}")
            
            # Stop the node first
            await self.stop()
            
            # Call the on_destroy hook
            await self.on_destroy()
            
            self.logger.info(f"Node {self.id} destroyed")
        except Exception as e:
            self.logger.error(f"Error destroying node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def on_create(self) -> None:
        """
        Hook called when the node is created.
        
        Override this method to implement custom creation logic.
        """
        pass

    async def on_start(self) -> None:
        """
        Hook called when the node is started.
        
        Override this method to implement custom start logic.
        """
        pass

    async def on_stop(self) -> None:
        """
        Hook called when the node is stopped.
        
        Override this method to implement custom stop logic.
        """
        pass

    async def on_status(self, msg: Any) -> None:
        """
        Hook called when a status message is received.
        
        Args:
            msg: The status message
        """
        try:
            self.logger.debug(f"Status message received for node {self.id}: {msg}")
            # Implementation depends on status message handling
        except Exception as e:
            self.logger.error(f"Error handling status message for node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def on_tick(self) -> None:
        """
        Hook called on timer ticks.
        
        Override this method to implement custom tick logic.
        """
        try:
            self.logger.debug(f"Tick for node {self.id}")
            # Implementation depends on tick handling
        except Exception as e:
            self.logger.error(f"Error in tick handler for node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def on_destroy(self) -> None:
        """
        Hook called when the node is destroyed.
        
        Override this method to implement custom destruction logic.
        """
        pass

    async def on_error(self, err: Exception) -> None:
        """
        Hook called when an error occurs.
        
        Args:
            err: The exception that occurred
        """
        self.logger.error(f"Error in node {self.id}: {str(err)}")
        self.logger.debug(f"Exception details: {traceback.format_exc()}")

    async def on_input(self, msg: Any) -> None:
        """
        Hook called when an input message is received.
        
        Args:
            msg: The input message
        """
        pass

    async def on_settings(self, msg: Any) -> None:
        """
        Hook called when settings are updated.
        
        Args:
            msg: The settings message
        """
        try:
            self.logger.debug(f"Settings update received for node {self.id}")
            
            # Update settings from message
            if isinstance(msg, dict):
                self.settings.update(msg)
            elif hasattr(msg, 'data') and msg.data:
                try:
                    settings_data = json.loads(msg.data)
                    self.settings.update(settings_data)
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON in settings message for node {self.id}")
                    
            # Call state changed hook
            await self.on_state_changed()
            
            self.logger.debug(f"Settings updated for node {self.id}: {self.settings}")
        except Exception as e:
            self.logger.error(f"Error updating settings for node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.__on_error(e)

    async def on_state_changed(self) -> None:
        """
        Hook called when the node's state changes.
        
        Override this method to implement custom state change logic.
        """
        pass

    async def __on_error(self, err: Exception) -> None:
        """
        Internal error handler.
        
        Args:
            err: The exception that occurred
        """
        try:
            # Call the user-defined error handler
            await self.on_error(err)
            
            # Publish the error to the service
            await self.service.publish(f"node/{self.id}/error", {"error": str(err)})
        except Exception as e:
            # If the error handler itself fails, log it but don't recurse
            self.logger.error(f"Error in error handler for node {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")


class NodeSync:
    """
    Synchronous version of the Node class.
    
    This class provides a synchronous interface for nodes in the Flux system,
    using threading instead of asyncio for concurrency.
    """
    id: str
    state: Dict[str, Any]
    logger: Logger
    service: 'Service'
    outputs: Dict[str, 'Output'] = field(default_factory=dict)
    inputs: Dict[str, 'Input'] = field(default_factory=dict)
    input_tasks: List[threading.Thread]
    node: DataNode
    timer: Optional[DataTimer]
    status_callback_on_stop: Optional[Callable[[], None]]
    status_callback_on_start: Optional[Callable[[], None]]
    status: str
    settings: Dict[str, Any] = field(default_factory=dict)
    _tick_thread: Optional[threading.Thread] = None
    _running: bool = False

    def __init__(self,
                 service: 'Service',
                 node_id: str,
                 node: DataNode,
                 logger: Optional[Logger] = None,
                 state: Optional[StateSlice] = None,
                 timer: Optional[DataTimer] = None,
                 on_tick: Optional[Callable[[], None]] = None,
                 status_factory: Optional[NodeStatus] = None):
        """
        Initialize a new NodeSync.
        
        Args:
            service: The service managing this node
            node_id: Unique identifier for this node
            node: Configuration for this node
            logger: Logger for node logs
            state: StateSlice for node state
            timer: Timer configuration
            on_tick: Callback for timer ticks
            status_factory: Factory for status values
        """
        self.id = node_id
        self.service = service
        self.node = node
        self.timer = timer
        self.on_tick_callback = on_tick
        self.input_tasks = []
        
        # Set up logger
        if logger is None:
            self.logger = getLogger(f"node.{node_id}")
        else:
            self.logger = logger
            
        # Set up state
        if state is None:
            self.state = StateSlice(state=None, prefix=f"node/{node_id}")
        else:
            self.state = state
            
        # Set up status factory
        if status_factory is None:
            self.status_factory = NodeStatus()
        else:
            self.status_factory = status_factory
            
        # Initialize status
        self.status = self.status_factory.created()
        
        # Initialize settings from node configuration
        if hasattr(node, 'settings') and node.settings:
            self.settings = node.settings.copy()
        else:
            self.settings = {}
            
        # Set up inputs
        self.inputs = {}
        if hasattr(node, 'inputs') and node.inputs:
            for input_data in node.inputs:
                input_obj = Input(input_data, node, service)
                self.inputs[input_obj.alias] = input_obj
                
        # Set up outputs
        self.outputs = {}
        if hasattr(node, 'outputs') and node.outputs:
            for output_data in node.outputs:
                output_obj = Output(output_data, node, service)
                self.outputs[output_obj.alias] = output_obj
                
        self.logger.info(f"NodeSync {node_id} initialized")

    def set_status(self, status: str) -> None:
        """
        Update the node's status.
        
        Args:
            status: The new status value
        """
        self.status = status
        self.logger.debug(f"NodeSync {self.id} status set to {status}")
        self.on_state_changed()

    def input(self, alias: str) -> 'Input':
        """
        Get an input by alias.
        
        Args:
            alias: The alias of the input
            
        Returns:
            The input object
        """
        if alias not in self.inputs:
            self.logger.warning(f"Input '{alias}' not found in node {self.id}")
            raise KeyError(f"Input '{alias}' not found")
        return self.inputs[alias]

    def output(self, alias: str) -> 'Output':
        """
        Get an output by alias.
        
        Args:
            alias: The alias of the output
            
        Returns:
            The output object
        """
        if alias not in self.outputs:
            self.logger.warning(f"Output '{alias}' not found in node {self.id}")
            raise KeyError(f"Output '{alias}' not found")
        return self.outputs[alias]

    def get_global_topic(self) -> str:
        """
        Get the global topic for this node.
        
        Returns:
            The global topic string
        """
        return f"node/{self.id}"

    def init(self) -> None:
        """
        Initialize the node.
        
        This method sets up the node's inputs and outputs and
        calls the on_create hook.
        """
        try:
            self.logger.info(f"Initializing NodeSync {self.id}")
            
            # Call the on_create hook
            self.on_create()
            
            # Set the initial status
            self.set_status(self.status_factory.created())
            
            # Notify the service of the node's status
            # Note: This is synchronous, so we're using a direct call
            self.service.send_node_state(self.id, self.status)
            
            self.logger.info(f"NodeSync {self.id} initialized")
        except Exception as e:
            self.logger.error(f"Error initializing NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            self.__on_error(e)

    def start(self) -> None:
        """
        Start the node.
        
        This method starts the node's inputs and timer and
        calls the on_start hook.
        """
        try:
            self.logger.info(f"Starting NodeSync {self.id}")
            
            # Set running flag
            self._running = True
            
            # Start the timer if configured
            if not self.service.opts.hasGlobalTick and self.timer:
                self._tick_thread = threading.Thread(
                    target=self._tick_loop, 
                    daemon=True,
                    name=f"tick-{self.id}"
                )
                self._tick_thread.start()
                self.logger.debug(f"Started timer for NodeSync {self.id}")
            elif self.service.opts.hasGlobalTick and self.on_tick_callback:
                # Subscribe to global tick
                self.service.subscribe(self.get_global_topic(), self.on_tick_callback)
                self.logger.debug(f"Subscribed to global tick for NodeSync {self.id}")
            
            # Call the on_start hook
            self.on_start()
            
            # Set the status to started
            self.set_status(self.status_factory.started())
            
            # Call the status callback if provided
            if self.status_callback_on_start:
                self.status_callback_on_start()
                
            self.logger.info(f"NodeSync {self.id} started")
        except Exception as e:
            self.logger.error(f"Error starting NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            self.__on_error(e)

    def _tick_loop(self) -> None:
        """
        Run the timer tick loop.
        
        This method runs a loop that calls the on_tick hook
        at the configured interval.
        """
        if not self.timer:
            return
            
        try:
            while self._running:
                if self.on_tick_callback:
                    self.on_tick_callback()
                else:
                    self.on_tick()
                time.sleep(self.timer.interval / 1000.0)  # Convert ms to seconds
        except Exception as e:
            self.logger.error(f"Error in tick loop for NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            self.__on_error(e)

    def stop(self) -> None:
        """
        Stop the node.
        
        This method stops the node's inputs and timer and
        calls the on_stop hook.
        """
        try:
            self.logger.info(f"Stopping NodeSync {self.id}")
            
            # Set running flag to false to stop tick loop
            self._running = False
            
            # Call the on_stop hook
            self.on_stop()
            
            # Wait for input tasks to finish
            for task in self.input_tasks:
                task.join(timeout=1.0)  # Wait with timeout to avoid hanging
                
            # Clear the input tasks list
            self.input_tasks.clear()
            
            # Unsubscribe from topics
            if hasattr(self, 'input_topics'):
                for topic in self.input_topics:
                    self.service.unsubscribe(topic)
            
            # Set the status to stopped
            self.set_status(self.status_factory.stopped())
            
            # Call the status callback if provided
            if self.status_callback_on_stop:
                self.status_callback_on_stop()
                
            self.logger.info(f"NodeSync {self.id} stopped")
        except Exception as e:
            self.logger.error(f"Error stopping NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            self.__on_error(e)

    def destroy(self) -> None:
        """
        Destroy the node.
        
        This method stops the node and calls the on_destroy hook.
        """
        try:
            self.logger.info(f"Destroying NodeSync {self.id}")
            
            # Stop the node first
            self.stop()
            
            # Call the on_destroy hook
            self.on_destroy()
            
            self.logger.info(f"NodeSync {self.id} destroyed")
        except Exception as e:
            self.logger.error(f"Error destroying NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            self.__on_error(e)

    def on_create(self) -> None:
        """
        Hook called when the node is created.
        
        Override this method to implement custom creation logic.
        """
        pass

    def on_start(self) -> None:
        """
        Hook called when the node is started.
        
        Override this method to implement custom start logic.
        """
        pass

    def on_stop(self) -> None:
        """
        Hook called when the node is stopped.
        
        Override this method to implement custom stop logic.
        """
        pass

    def on_tick(self) -> None:
        """
        Hook called on timer ticks.
        
        Override this method to implement custom tick logic.
        """
        pass

    def on_destroy(self) -> None:
        """
        Hook called when the node is destroyed.
        
        Override this method to implement custom destruction logic.
        """
        pass

    def on_error(self, err: Exception) -> None:
        """
        Hook called when an error occurs.
        
        Args:
            err: The exception that occurred
        """
        self.logger.error(f"Error in NodeSync {self.id}: {str(err)}")

    def on_input(self, topic: str, msg: Any) -> None:
        """
        Hook called when an input message is received.
        
        Args:
            topic: The topic the message was received on
            msg: The input message
        """
        pass

    def on_state_changed(self) -> None:
        """
        Hook called when the node's state changes.
        
        This method notifies the service of the node's status.
        """
        try:
            self.service.publish(f"node/{self.id}/status", {"status": self.status})
        except Exception as e:
            self.logger.error(f"Error publishing state change for NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")

    def __on_error(self, err: Exception) -> None:
        """
        Internal error handler.
        
        Args:
            err: The exception that occurred
        """
        try:
            # Call the user-defined error handler
            self.on_error(err)
            
            # Publish the error to the service
            self.service.publish(f"node/{self.id}/error", {"error": str(err)})
        except Exception as e:
            # If the error handler itself fails, log it but don't recurse
            self.logger.error(f"Error in error handler for NodeSync {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")


class Input:
    topics: List[str]
    input: DataInput
    alias: str
    service: 'Service'
    node: Node
    
    state: StateSlice = StateSlice(state=None, prefix=None)

    def __init__(self, input_data: Union[DataInput, Dict], node: Union[DataNode, Dict], service):
        self.input = input_data
        
        # Handle input_data as either a dictionary or DataInput object
        if isinstance(input_data, dict):
            self.topics = input_data.get('topics', [])
            self.alias = input_data.get('name', '')
        else:
            self.topics = getattr(input_data, 'topics', [])
            self.alias = getattr(input_data, 'name', getattr(input_data, 'alias', ''))
            
        self.service = service
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
    topics: List[str]
    service: 'Service'
    node: Node
    state: StateSlice = StateSlice(state=None, prefix=None)

    def __init__(self, output_data: Union[DataOutput, Dict], node, service):
        # Handle output_data as either a dictionary or DataOutput object
        if isinstance(output_data, dict):
            self.topics = output_data.get('topics', [])
            self.alias = output_data.get('name', '')
        else:
            self.topics = getattr(output_data, 'topics', [])
            self.alias = getattr(output_data, 'name', getattr(output_data, 'alias', ''))
            
        self.service = service
        self.node = node
    
    async def publish(self, data):
        for topic in self.topics:
            await self.service.publish(topic.replace("/", "."), data)
        return

    async def call(self, path, callback):
        return self.service.call(path, callback)