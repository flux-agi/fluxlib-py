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

## Core Components

### Service

The `Service` class is the central component that manages nodes and handles messaging:

```python
from fluxlib.service import Service, ServiceOptions

# Create with default options
service = Service(service_id="my-service")

# Create with custom options
options = ServiceOptions(hasGlobalTick=True, tickInterval=500)
service = Service(service_id="my-service", opts=options)
```

Key methods:
- `attach(transport, topic, status)`: Connect the service to a transport
- `run()`: Start the service and subscribe to service-level topics
- `append_node(node)`: Add a node to the service
- `publish(topic, message)`: Send a message to a topic
- `subscribe(topic)`: Subscribe to a topic and get a queue for messages
- `subscribe_handler(topic, handler)`: Subscribe to a topic with a handler function

### Node

The `Node` class represents a modular component with a defined lifecycle:

```python
from fluxlib.node import Node

class MyNode(Node):
    async def on_init(self):
        # Called when the node is initialized
        pass
        
    async def on_start(self):
        # Called when the node is started
        pass
        
    async def on_stop(self):
        # Called when the node is stopped
        pass
        
    async def on_tick(self, time):
        # Called periodically if global tick is enabled
        pass
```

### State Management

FluxLib provides flexible state management through the `StateSlice` class:

```python
from fluxlib.state import StateSlice

# Create a state slice
state = StateSlice()

# Set and get values
state.set("key", "value")
value = state.get("key")
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

