# FluxLib Python SDK

FluxLib is a powerful SDK for building distributed, message-based applications in the Flux ecosystem. It provides a robust framework for creating services and nodes that communicate via a message broker (such as NATS).

## Features

- **Service-based Architecture**: Create and manage services that coordinate multiple nodes
- **Node Management**: Build modular components with clear lifecycle management
- **Message Passing**: Seamless communication between services and nodes
- **State Management**: Flexible state handling for your application components
- **Transport Abstraction**: Support for different message brokers (primarily NATS)

## Installation

### From GitHub

```shell
pip install git+https://github.com/flux-agi/fluxlib-py.git
```

### Local Development

For local development, clone the repository and install in editable mode:

```shell
git clone https://github.com/flux-agi/fluxlib-py.git
cd fluxlib-py
pip install -e .
```

## Quick Start

Here's a simple example of creating a service with a node:

```python
import asyncio
from fluxlib.service import Service, ServiceOptions
from fluxlib.node import Node
from fluxmq.adapter.nats import Nats
from fluxmq.topic import Topic
from fluxmq.status import Status

# Create a service
service = Service(service_id="my-service")

# Create a transport (using NATS)
transport = Nats()
await transport.connect("nats://localhost:4222")

# Attach transport to service
service.attach(transport, Topic(), Status())

# Define a node
class MyNode(Node):
    async def on_start(self):
        print("Node started!")
        # Publish a message
        await self.service.publish("my-topic", {"message": "Hello from MyNode!"})
    
    async def on_stop(self):
        print("Node stopped!")

# Add node to service
my_node = MyNode(node_id="my-node", service=service)
service.append_node(my_node)

# Run the service
await service.run()
```

## API Reference

### Service Class

The `Service` class is the central component that manages nodes and handles messaging.

#### Constructor

```python
Service(service_id: str = "UndefinedID", 
        logger: Logger = None, 
        state: StateSlice = StateSlice(state=None, prefix=None), 
        opts: ServiceOptions = None)
```

- `service_id`: Unique identifier for the service
- `logger`: Optional custom logger
- `state`: Optional state slice for service state management
- `opts`: Optional service configuration options

**Example:**
```python
from fluxlib.service import Service, ServiceOptions
from logging import getLogger

# Create with default options
service = Service(service_id="my-service")

# Create with custom options
options = ServiceOptions(hasGlobalTick=True)
custom_logger = getLogger("my-service-logger")
service = Service(
    service_id="my-service", 
    logger=custom_logger,
    opts=options
)
```

#### Core Methods

| Method | Description |
|--------|-------------|
| `attach(transport, topic, status)` | Attaches low-level implementation of main abstractions (transport, topic, status) |
| `run()` | Connects to the transport and subscribes to service-level topics |
| `append_node(node)` | Adds a node to the service |
| `publish(topic, message)` | Sends a message to a topic |
| `subscribe(topic)` | Subscribes to a topic and returns a queue for messages |
| `subscribe_handler(topic, handler)` | Subscribes to a topic with a handler function |
| `unsubscribe(topic)` | Unsubscribes from a topic |
| `request(topic, payload)` | Sends a request to a topic and waits for a response |
| `respond(message, response)` | Responds to a request message |
| `send_status(status)` | Sends a status update for the service |

**Examples:**

```python
# Attaching transport to service
from fluxmq.adapter.nats import Nats
from fluxmq.topic import Topic
from fluxmq.status import Status

transport = Nats()
await transport.connect("nats://localhost:4222")
service.attach(transport, Topic(), Status())

# Publishing a message
await service.publish("my-topic", {"data": "Hello, world!"})

# Subscribing to a topic with a handler
async def message_handler(message):
    print(f"Received message: {message.data}")
    
await service.subscribe_handler("my-topic", message_handler)

# Making a request and waiting for response
response = await service.request("request-topic", {"query": "What's the weather?"})
print(f"Got response: {response.data}")

# Responding to a request
async def request_handler(message):
    await service.respond(message, {"answer": "It's sunny!"})
    
await service.subscribe_handler("request-topic", request_handler)
```

#### Node Management Methods

| Method | Description |
|--------|-------------|
| `start_node(node_id)` | Starts a specific node by ID |
| `start_node_all()` | Starts all nodes in the service |
| `stop_node(node_id)` | Stops a specific node by ID |
| `stop_node_all()` | Stops all nodes in the service |
| `destroy_node(node_id)` | Destroys a specific node by ID |
| `destroy_node_all()` | Destroys all nodes in the service |

**Example:**
```python
# Starting and stopping specific nodes
await service.start_node("processor-node")
await service.stop_node("processor-node")

# Starting and stopping all nodes
await service.start_node_all()
await service.stop_node_all()

# Destroying nodes
await service.destroy_node("temporary-node")
await service.destroy_node_all()  # Clean up all nodes
```

#### Lifecycle Event Handlers

| Method | Description |
|--------|-------------|
| `on_init(message)` | Handler for initialization events |
| `on_connected(message)` | Handler for connection events |
| `on_ready(message)` | Handler for ready events |
| `on_start(message)` | Handler for start events |
| `on_stop(message)` | Handler for stop events |
| `on_restart(message)` | Handler for restart events |
| `on_settings(message)` | Handler for settings events |
| `on_config(message)` | Handler for configuration events |
| `on_tick(time)` | Handler for tick events |
| `on_shutdown(signal_number, frame)` | Handler for shutdown events |
| `on_error(message)` | Handler for error events |

**Example:**
```python
# Customizing service lifecycle handlers by subclassing
from fluxlib.service import Service

class MyService(Service):
    async def on_init(self, message):
        print(f"Service {self.id} initialized with config: {message.data}")
        
    async def on_start(self, message):
        print(f"Service {self.id} started")
        
    async def on_stop(self, message):
        print(f"Service {self.id} stopped")
        
    async def on_error(self, message):
        print(f"Error in service {self.id}: {message.data}")
```

### Node Class

The `Node` class represents a modular component with a defined lifecycle.

#### Constructor

```python
Node(service: Service, 
     node_id: str, 
     node: DataNode, 
     logger: Logger = None, 
     state: StateSlice = None, 
     timer: DataTimer = None, 
     on_tick: Optional[Callable[[], None]] = None, 
     status_factory: NodeStatus = NodeStatus())
```

- `service`: The service this node belongs to
- `node_id`: Unique identifier for the node
- `node`: DataNode configuration object
- `logger`: Optional custom logger
- `state`: Optional state slice for node state management
- `timer`: Optional timer configuration
- `on_tick`: Optional callback for tick events
- `status_factory`: Optional custom status factory

**Example:**
```python
from fluxlib.node import Node, DataNode, DataInput, DataOutput, DataTimer
from fluxlib.state import StateSlice

# Create node configuration
node_config = DataNode(
    id="processor-node",
    type="processor",
    settings={"batch_size": 100},
    inputs=[DataInput(topics=["raw-data"], alias="input")],
    outputs=[DataOutput(topics=["processed-data"], alias="output")]
)

# Create timer for periodic processing
timer = DataTimer(type="interval", interval=1000)  # 1000ms interval

# Create node with custom state
node_state = StateSlice(prefix="processor")
processor_node = Node(
    service=service,
    node_id="processor-node",
    node=node_config,
    state=node_state,
    timer=timer
)

# Add to service
service.append_node(processor_node)
```

#### Core Methods

| Method | Description |
|--------|-------------|
| `set_status(status)` | Sets the node's status |
| `input(alias)` | Gets an input by alias |
| `output(alias)` | Gets an output by alias |
| `get_global_topic()` | Gets the global topic for this node |

**Example:**
```python
# Inside a node method
async def process_data(self):
    # Get input and output by alias
    input_handler = self.input("input")
    output_handler = self.output("output")
    
    # Read data from input
    data = input_handler.read()
    
    # Process data
    processed_data = self.transform(data)
    
    # Publish to output
    await output_handler.publish(processed_data)
    
    # Update node status
    self.set_status("processing_complete")
```

#### Lifecycle Methods

| Method | Description |
|--------|-------------|
| `init()` | Initializes the node |
| `start()` | Starts the node and its tick loop if configured |
| `stop()` | Stops the node and its tick loop |
| `destroy()` | Destroys the node |

**Example:**
```python
# Manually controlling node lifecycle
await node.init()  # Initialize the node
await node.start()  # Start the node

# Later
await node.stop()   # Stop the node
await node.destroy()  # Clean up resources
```

#### Lifecycle Event Handlers

| Method | Description |
|--------|-------------|
| `on_create()` | Handler for node creation |
| `on_start()` | Handler for node start |
| `on_stop()` | Handler for node stop |
| `on_tick()` | Handler for tick events |
| `on_destroy()` | Handler for node destruction |
| `on_error(err)` | Handler for error events |
| `on_input(msg)` | Handler for input messages |
| `on_settings(msg)` | Handler for settings updates |
| `on_state_changed()` | Handler for state change events |

**Example:**
```python
# Implementing a custom node with lifecycle handlers
from fluxlib.node import Node

class ProcessorNode(Node):
    async def on_create(self):
        print(f"Node {self.id} created")
        # Initialize resources
        self.processor = self.initialize_processor()
        
    async def on_start(self):
        print(f"Node {self.id} started")
        # Start processing
        self.input("input").listen()
        
    async def on_input(self, msg):
        # Process incoming message
        result = self.processor.process(msg.data)
        # Send to output
        await self.output("output").publish(result)
        
    async def on_tick(self):
        # Periodic processing
        await self.check_queue_health()
        
    async def on_stop(self):
        print(f"Node {self.id} stopped")
        # Clean up resources
        
    async def on_destroy(self):
        print(f"Node {self.id} destroyed")
        # Release all resources
        self.processor.shutdown()
        
    async def on_error(self, err):
        print(f"Error in node {self.id}: {str(err)}")
        # Handle error
```

### Input and Output Classes

The `Input` and `Output` classes handle node communication.

#### Input Methods

| Method | Description |
|--------|-------------|
| `listen()` | Starts listening for messages on the input topics |
| `store_value(value)` | Stores a value in the input's state |
| `read()` | Reads the current value from the input's state |
| `subscribe(callback)` | Subscribes to all input topics with a callback |
| `subscribe_one(topic, callback)` | Subscribes to a specific topic with a callback |

**Example:**
```python
# Inside a node method
async def setup_input_handling(self):
    # Get input by alias
    data_input = self.input("data")
    
    # Start listening for messages
    data_input.listen()
    
    # Or subscribe with a custom callback
    async def process_data(message):
        print(f"Processing data: {message.data}")
        processed = self.process(message.data)
        data_input.store_value(processed)
    
    await data_input.subscribe(process_data)
    
    # Or subscribe to a specific topic
    await data_input.subscribe_one("specific-topic", process_data)
    
    # Later, read the latest value
    latest_data = data_input.read()
    print(f"Latest data: {latest_data}")
```

#### Output Methods

| Method | Description |
|--------|-------------|
| `publish(data)` | Publishes data to all output topics |
| `call(path, callback)` | Calls a specific path with a callback |

**Example:**
```python
# Inside a node method
async def send_results(self, results):
    # Get output by alias
    results_output = self.output("results")
    
    # Publish to all configured topics
    await results_output.publish({
        "timestamp": time.time(),
        "data": results
    })
    
    # Call a specific path with a callback
    async def handle_response(response):
        print(f"Got response: {response}")
    
    await results_output.call("process/complete", handle_response)
```

### State Management

FluxLib provides flexible state management through the `StateSlice` class.

#### Constructor

```python
StateSlice(state: Optional[Dict[str, Any]] = None, prefix: Optional[str] = None)
```

- `state`: Optional initial state dictionary
- `prefix`: Optional prefix for state keys

**Example:**
```python
from fluxlib.state import StateSlice

# Create a state slice with initial values
initial_state = {
    "counter": 0,
    "last_updated": None
}
state = StateSlice(state=initial_state, prefix="my-node")

# Create a state slice that shares the same underlying state
# but with a different prefix
child_state = StateSlice(state=state._state, prefix="my-node.child")
```

#### Methods

| Method | Description |
|--------|-------------|
| `get(key, default=None)` | Gets a value from the state |
| `set(key, val, opts=None)` | Sets a value in the state |
| `delete(key)` | Deletes a key from the state |
| `reset()` | Resets the state to its initial empty condition |
| `get_all_with_prefix()` | Gets all state values with the current prefix |

**Example:**
```python
# Using state in a node
from fluxlib.state import StateSlice

# Create a state slice
state = StateSlice(prefix="counter")

# Set values
state.set("count", 0)
state.set("last_updated", time.time())

# Get values
current_count = state.get("count", 0)  # Default to 0 if not found
print(f"Current count: {current_count}")

# Update values
state.set("count", current_count + 1)
state.set("last_updated", time.time())

# Get all values with the current prefix
all_state = state.get_all_with_prefix()
print(f"All state: {all_state}")

# Delete a value
state.delete("temporary_value")

# Reset the state
state.reset()
```

## Best Practices

1. **Service Organization**: Create a single service per application, with multiple nodes for different functionalities
2. **Error Handling**: Implement proper error handling in node methods to prevent service crashes
3. **Message Structure**: Use consistent message structures for better interoperability
4. **State Management**: Use state slices to isolate state between different components
5. **Connection Management**: Always ensure the transport is connected before subscribing to topics

## Troubleshooting

### Connection Issues

If you're experiencing connection issues with the NATS server:

1. Ensure the NATS server is running and accessible
2. Check that the connection URL is correct
3. Verify that the service is connecting to the transport before subscribing to topics

Example of robust connection handling:

```python
from fluxmq.adapter.nats import Nats

transport = Nats()
try:
    await transport.connect(
        "nats://localhost:4222",
        reconnect_time_wait=2,
        max_reconnect_attempts=10,
        connect_timeout=10
    )
    print("Successfully connected to NATS server")
except Exception as e:
    print(f"Failed to connect to NATS server: {str(e)}")
```

## Examples

FluxLib comes with example scripts to help you get started:

### Echo Service Example

The `simple_service.py` example demonstrates how to create a service with an echo node that responds to messages:

```shell
# Run the echo service
cd examples
python simple_service.py
```

This example shows:
- Creating a service and attaching a NATS transport
- Defining a node with lifecycle methods (init, start, stop)
- Subscribing to topics and handling messages
- Publishing responses

### Echo Client Example

The `echo_client.py` example shows how to create a client that interacts with the echo service:

```shell
# Run the echo client
cd examples
python echo_client.py
```

This example demonstrates:
- Connecting to NATS from a client application
- Sending requests to a service
- Subscribing to response topics
- Handling responses asynchronously

To run both examples together, start the service in one terminal and the client in another.

## Contributing

### Version Release

To release a new version:

```shell
cz bump
git push
```

After that, reinstall the package in your project.

## License

[Add license information here]

