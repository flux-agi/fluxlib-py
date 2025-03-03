from asyncio import Task
from dataclasses import dataclass
from logging import Logger, getLogger
from typing import Coroutine, Any, TypeVar, Generic, Callable, List, Dict, TYPE_CHECKING, Optional, Union

import asyncio
import json
import traceback
from types import SimpleNamespace

from asyncio.queues import Queue

from fluxmq.message import Message
from fluxmq.topic import Topic
from fluxmq.transport import Transport, SyncTransport
from fluxmq.status import Status

from fluxlib.state import StateSlice

MessageType = TypeVar('Message', bound=Message)

class TypedQueue(Queue, Generic[MessageType]):
    """A typed queue for handling specific message types."""
    pass

if TYPE_CHECKING:
    from fluxlib.node import Node

@dataclass
class ServiceOptions:
    """Configuration options for a Service."""
    hasGlobalTick: bool = False
    tickInterval: int = 1000  # Default tick interval in milliseconds

class Service:
    """
    Main service class for managing nodes and handling messaging.
    
    This class provides the core functionality for creating and managing nodes,
    handling message subscriptions, and coordinating communication between nodes.
    """
    state: Dict[str, Any]
    transport: Transport
    topic: Topic
    status: Status
    opts: ServiceOptions
    id: str
    nodes: List['Node'] = []
    _subscriptions: Dict[str, TypedQueue] = {}
    _handlers: Dict[str, Task] = {}
    

    def __init__(self,
                 service_id: str = "UndefinedID",
                 logger: Logger = None,
                 state: StateSlice = None,
                 opts: ServiceOptions = None):
        """
        Initialize a new Service instance.
        
        Args:
            service_id: Unique identifier for this service
            logger: Logger instance for service logs
            state: StateSlice for managing service state
            opts: Service configuration options
        """
        self.id = service_id
        self.opts = opts or ServiceOptions()
        self.state = state or StateSlice(state=None, prefix=None)
        if logger is None:
            self.logger = getLogger()
        else:
            self.logger = logger
        self.nodes = []
        self._subscriptions = {}
        self._handlers = {}
        
        self.logger.info(f"Service {self.id} initialized")

    def attach(self,
               transport: Transport,
               topic: Topic,
               status: Status) -> None:
        """
        Attach transport, topic, and status handlers to the service.
        
        Args:
            transport: Transport layer for message passing
            topic: Topic handler for message routing
            status: Status handler for service status
        """
        self.transport = transport
        self.topic = topic
        self.status = status
        
        self.logger.debug(f"Service {self.id} attached to transport")

    async def run(self) -> None:
        """
        Run the service and initialize all nodes.
        
        This method starts the service, initializes all nodes, and sets up
        message handlers for service-level events.
        """
        try:
            self.logger.info(f"Starting service {self.id}")
            
            # Subscribe to service-level topics
            await self.subscribe_handler(f"service/{self.id}/init", self.on_init)
            await self.subscribe_handler(f"service/{self.id}/connected", self.on_connected)
            await self.subscribe_handler(f"service/{self.id}/ready", self.on_ready)
            await self.subscribe_handler(f"service/{self.id}/start", self.on_start)
            await self.subscribe_handler(f"service/{self.id}/stop", self.on_stop)
            await self.subscribe_handler(f"service/{self.id}/restart", self.on_restart)
            await self.subscribe_handler(f"service/{self.id}/settings", self.on_settings)
            await self.subscribe_handler(f"service/{self.id}/config", self.on_config)
            await self.subscribe_handler(f"service/{self.id}/tick", self.on_tick)
            await self.subscribe_handler(f"service/{self.id}/error", self.on_error)
            await self.subscribe_handler(f"service/{self.id}/get_common_data", self.on_get_common_data)
            await self.subscribe_handler(f"service/{self.id}/ide_status", self.on_ide_status)
            
            # Initialize all nodes
            await self.init()
            
            self.logger.info(f"Service {self.id} running")
        except Exception as e:
            self.logger.error(f"Error starting service {self.id}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            raise

    async def destroy_node_all(self) -> None:
        """Destroy all nodes managed by this service."""
        for node in self.nodes:
            await self.destroy_node(node.id)

    async def start_node_all(self) -> None:
        """Start all nodes managed by this service."""
        for node in self.nodes:
            await self.start_node(node.id)

    async def stop_node_all(self) -> None:
        """Stop all nodes managed by this service."""
        for node in self.nodes:
            await self.stop_node(node.id)

    async def destroy_node(self, node_id: str) -> None:
        """
        Destroy a specific node by ID.
        
        Args:
            node_id: ID of the node to destroy
        """
        for node in self.nodes:
            if node.id == node_id:
                await node.destroy()
                self.nodes.remove(node)
                self.logger.info(f"Node {node_id} destroyed")
                return
        
        self.logger.warning(f"Node {node_id} not found for destruction")

    async def request_config(self):
        """Request configuration from the service manager."""
        await self.publish(f"service/{self.id}/request_config", {})
        self.logger.debug(f"Configuration requested for service {self.id}")

    async def on_get_common_data(self, message: MessageType):
        """
        Handle requests for common service data.
        
        Args:
            message: The request message
        """
        # Implementation depends on what common data should be shared
        pass

    async def on_ide_status(self, message: MessageType):
        """
        Handle IDE status updates.
        
        Args:
            message: The status update message
        """
        # Implementation depends on IDE integration
        pass

    async def start_node(self, node_id: str) -> None:
        """
        Start a specific node by ID.
        
        Args:
            node_id: ID of the node to start
        """
        for node in self.nodes:
            if node.id == node_id:
                await node.start()
                self.logger.info(f"Node {node_id} started")
                return
                
        self.logger.warning(f"Node {node_id} not found for starting")

    async def stop_node(self, node_id: str) -> None:
        """
        Stop a specific node by ID.
        
        Args:
            node_id: ID of the node to stop
        """
        for node in self.nodes:
            if node.id == node_id:
                await node.stop()
                self.logger.info(f"Node {node_id} stopped")
                return
                
        self.logger.warning(f"Node {node_id} not found for stopping")

    def append_node(self, node: 'Node') -> None:
        """
        Add a node to this service.
        
        Args:
            node: The node to add
        """
        self.nodes.append(node)
        self.logger.debug(f"Node {node.id} added to service {self.id}")

    async def subscribe(self, topic: str) -> TypedQueue:
        """
        Subscribe to a topic and return a queue for messages.
        
        Args:
            topic: The topic to subscribe to
            
        Returns:
            A queue that will receive messages for this topic
        """
        if topic in self._subscriptions:
            return self._subscriptions[topic]
            
        queue: TypedQueue[MessageType] = TypedQueue()
        self._subscriptions[topic] = queue
        
        await self.transport.subscribe(topic, lambda msg: queue.put_nowait(msg))
        self.logger.debug(f"Subscribed to topic: {topic}")
        
        return queue

    async def subscribe_handler(self, topic: str, handler: Callable[[MessageType], Coroutine[Any, Any, None]]) -> Task:
        """
        Subscribe to a topic with a handler function.
        
        Args:
            topic: The topic to subscribe to
            handler: Async function to handle messages
            
        Returns:
            Task handling the subscription
        """
        queue = await self.subscribe(topic)
        
        async def read_queue(queue: TypedQueue[MessageType]):
            while True:
                try:
                    msg = await queue.get()
                    await handler(msg)
                    queue.task_done()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in handler for topic {topic}: {str(e)}")
                    self.logger.debug(f"Exception details: {traceback.format_exc()}")
        
        task = asyncio.create_task(read_queue(queue))
        self._handlers[topic] = task
        return task

    async def unsubscribe(self, topic: str):
        """
        Unsubscribe from a topic.
        
        Args:
            topic: The topic to unsubscribe from
        """
        if topic in self._handlers:
            self._handlers[topic].cancel()
            del self._handlers[topic]
            
        if topic in self._subscriptions:
            del self._subscriptions[topic]
            
        await self.transport.unsubscribe(topic)
        self.logger.debug(f"Unsubscribed from topic: {topic}")

    async def publish(self, topic: str, message: Any):
        """
        Publish a message to a topic.
        
        Args:
            topic: The topic to publish to
            message: The message to publish
        """
        try:
            payload = json.dumps(message) if not isinstance(message, bytes) else message
            await self.transport.publish(topic, payload)
            self.logger.debug(f"Published to topic: {topic}")
        except Exception as e:
            self.logger.error(f"Error publishing to topic {topic}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")

    async def request(self, topic: str, payload: Any):
        """
        Send a request and wait for a response.
        
        Args:
            topic: The topic to send the request to
            payload: The request payload
            
        Returns:
            The response message
        """
        try:
            data = json.dumps(payload) if not isinstance(payload, bytes) else payload
            response = await self.transport.request(topic, data)
            return response
        except Exception as e:
            self.logger.error(f"Error requesting from topic {topic}: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            raise

    async def respond(self, message: MessageType, response: bytes):
        """
        Respond to a request message.
        
        Args:
            message: The request message to respond to
            response: The response data
        """
        try:
            await self.transport.respond(message, response)
            self.logger.debug(f"Responded to message")
        except Exception as e:
            self.logger.error(f"Error responding to message: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")

    async def send_status(self, status: str):
        """
        Send a service status update.
        
        Args:
            status: The status to send
        """
        await self.publish(f"service/{self.id}/status", {"status": status})
        self.logger.debug(f"Service status sent: {status}")

    async def send_common_data(self, message: Any):
        """
        Send common data to the service manager.
        
        Args:
            message: The data to send
        """
        await self.publish(f"service/{self.id}/common_data", message)
        self.logger.debug(f"Common data sent")

    async def send_node_state(self, node_id: str, status: str):
        """
        Send a node status update.
        
        Args:
            node_id: The ID of the node
            status: The status to send
        """
        await self.publish(f"node/{node_id}/status", {"status": status})
        self.logger.debug(f"Node {node_id} status sent: {status}")

    async def on_init(self, message: MessageType) -> None:
        """
        Handle service initialization message.
        
        Args:
            message: The initialization message
        """
        try:
            self.logger.info(f"Service {self.id} received init message")
            payload = json.loads(message.data)
            
            if "nodes" in payload:
                for node_data in payload["nodes"]:
                    await self.get_node(node_data)
                    
            await self.send_status("initialized")
        except Exception as e:
            self.logger.error(f"Error in service initialization: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.publish(f"service/{self.id}/error", {"error": str(e)})

    async def init(self) -> None:
        """
        Initialize the service and request configuration.
        
        This method is called during service startup to request initial
        configuration from the service manager.
        """
        # Request config with list of nodes
        await self.request_config()
        self.logger.info(f"Service {self.id} initialized")

    async def get_node(self, node_data: Any) -> None:
        """
        Process node data and create a node.
        
        Args:
            node_data: Data describing the node to create
        """
        # Implementation depends on node creation logic
        pass

    async def on_connected(self, message: MessageType) -> None:
        """
        Handle service connected message.
        
        Args:
            message: The connected message
        """
        self.logger.info(f"Service {self.id} connected")

    async def on_ready(self, message: MessageType) -> None:
        """
        Handle service ready message.
        
        Args:
            message: The ready message
        """
        self.logger.info(f"Service {self.id} ready")
        self.ready(message)

    def ready(self, message: MessageType) -> None:
        """
        Process ready state.
        
        Args:
            message: The ready message
        """
        # Implementation depends on ready state handling
        pass

    async def on_start(self, message: MessageType) -> None:
        """
        Handle service start message.
        
        Args:
            message: The start message
        """
        self.logger.info(f"Service {self.id} starting")
        await self.start_node_all()
        await self.send_status("started")

    async def on_stop(self, message: MessageType) -> None:
        """
        Handle service stop message.
        
        Args:
            message: The stop message
        """
        self.logger.info(f"Service {self.id} stopping")
        await self.stop_node_all()
        await self.send_status("stopped")

    async def on_restart(self, message: MessageType) -> None:
        """
        Handle service restart message.
        
        Args:
            message: The restart message
        """
        self.logger.info(f"Service {self.id} restarting")
        await self.stop_node_all()
        await self.start_node_all()
        await self.send_status("restarted")

    async def on_settings(self, message: MessageType) -> None:
        """
        Handle service settings message.
        
        Args:
            message: The settings message containing new settings
        """
        try:
            self.logger.info(f"Service {self.id} received settings update")
            payload = json.loads(message.data)
            # Process settings update
            self.logger.debug(f"Settings updated: {payload}")
        except Exception as e:
            self.logger.error(f"Error processing settings: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")

    async def on_config(self, message: MessageType) -> None:
        """
        Handle service configuration message.
        
        Args:
            message: The configuration message
        """
        try:
            self.logger.info(f"Service {self.id} received configuration")
            payload = json.loads(message.data)
            
            if "nodes" in payload:
                for node_data in payload["nodes"]:
                    await self.get_node(node_data)
                    
            await self.send_status("configured")
        except Exception as e:
            self.logger.error(f"Error processing configuration: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            await self.publish(f"service/{self.id}/error", {"error": str(e)})

    async def on_tick(self, time: int) -> None:
        """
        Handle tick message for time synchronization.
        
        Args:
            time: The current system time
        """
        # Implementation depends on tick handling
        pass

    async def on_shutdown(self, signal_number, frame) -> None:
        """
        Handle service shutdown.
        
        Args:
            signal_number: The signal number that triggered shutdown
            frame: The current stack frame
        """
        self.logger.info(f"Service {self.id} shutting down")
        await self.stop_node_all()
        await self.destroy_node_all()
        
        # Cancel all subscription handlers
        for topic, task in self._handlers.items():
            task.cancel()
            
        await self.send_status("shutdown")

    async def on_error(self, message: MessageType) -> None:
        """
        Handle error messages.
        
        Args:
            message: The error message
        """
        try:
            payload = json.loads(message.data)
            error = payload.get("error", "Unknown error")
            self.logger.error(f"Service error: {error}")
        except Exception as e:
            self.logger.error(f"Error processing error message: {str(e)}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")

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
        self.subscribe_handler(self.topic.ide_status(), self.on_ide_status)
        self.subscribe_handler(self.topic.restart_node(self.id), self.on_restart)
        self.subscribe_handler(self.topic.ide_status(), self.on_ide_status)
        self.subscribe_handler(self.topic.get_common_data(self.id), self.on_get_common_data)

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

    def subscribe(self, topic: str, handler: Callable[[MessageType], None]):

        if handler is not None:
            if handler not in self.subscriptions:
                sub = self.transport.subscribe(topic, handler)
                self.subscriptions.append(handler)
                
                return sub
            
        return self.transport.subscribe(topic, None)
        

    def subscribe_handler(self, topic, handler: Callable[[MessageType], None]) -> None:
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

    def respond(self, message: MessageType, response: bytes):
        self.transport.respond(message, response)
        return

    def send_status(self, status: str):
        topic = self.topic.status(self.id)
        self.transport.publish(topic, status)
    
    def request_config(self):
        self.transport.publish(self.topic.configuration_request(self.id), self.status.ready())

    def send_common_data(self, message):
        self.transport.publish(self.topic.set_common_data(self.id), message)

    def send_node_state(self, node_id: str, status: str):
        topic = self.topic.set_node_state(node_id)
        self.transport.publish(topic, status)

    def on_init(self,  message: MessageType) -> None:
        data = json.loads(message.payload)
        self.logger.debug(f"Received configuration {data}")
        
        # Check if the configuration has a 'nodes' field
        if 'nodes' in data:
            self.config = data['nodes']
        else:
            # If no 'nodes' field, assume it's a single node configuration
            self.config = [data]
            
        self.init()

    def init(self) -> None:
        # config with list of nodes
        if not self.config or not isinstance(self.config, list):
            self.logger.error(f"Invalid configuration format: {self.config}")
            return
            
        for node_data in self.config:
            node = self.get_node(node_data)
            self.nodes.append(node)
        # initialize service store

    def get_node(self, node_data: any) -> None:
        pass

    def on_connected(self, message: MessageType) -> None:
        pass

    def on_ide_status(self, message: MessageType) -> None:
        pass

    async def on_get_common_data(self, message: MessageType):
        pass

    def on_ready(self, message: MessageType) -> None:
        pass

    def ready(self, message: MessageType) -> None:
        pass

    def call(self, path, callback: Callable[[], None]) -> None:
        pass

    def on_start(self, message: MessageType) -> None:
        pass

    def on_stop(self, message: MessageType) -> None:
        pass

    def on_restart(self, message: MessageType) -> None:
        pass

    def on_settings(self, message: MessageType) -> None:
        pass

    def on_config(self, message: MessageType) -> None:
        pass

    def on_tick(self, time: int) -> None:
        pass

    def on_shutdown(self, signal_number, frame) -> None:
        pass

    def on_error (self, message: MessageType) -> None:
        pass