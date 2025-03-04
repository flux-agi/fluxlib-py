# FluxLib Examples

This directory contains example scripts that demonstrate how to use the FluxLib Python SDK.

## Prerequisites

Before running the examples, make sure you have:

1. A running NATS server
2. FluxLib and FluxMQ installed

If you don't have a NATS server running, you can start one using Docker:

```shell
docker run -d --name nats-server -p 4222:4222 -p 8222:8222 -p 6222:6222 nats
```

## Available Examples

### 1. Echo Service (`simple_service.py`)

This example demonstrates how to create a service with an echo node that responds to messages.

**Features demonstrated:**
- Creating a service and attaching a NATS transport
- Defining a node with lifecycle methods (init, start, stop)
- Subscribing to topics and handling messages
- Publishing responses

**How to run:**
```shell
# Set the NATS URL if needed (defaults to localhost)
export NATS_URL=nats://localhost:4222

# Run the service
python simple_service.py
```

### 2. Echo Client (`echo_client.py`)

This example shows how to create a client that interacts with the echo service.

**Features demonstrated:**
- Connecting to NATS from a client application
- Sending requests to a service
- Subscribing to response topics
- Handling responses asynchronously

**How to run:**
```shell
# Set the NATS URL if needed (defaults to localhost)
export NATS_URL=nats://localhost:4222

# Run the client
python echo_client.py
```

## Running the Examples Together

To see the full interaction between the service and client:

1. Open two terminal windows
2. In the first terminal, run the echo service:
   ```shell
   python simple_service.py
   ```
3. In the second terminal, run the echo client:
   ```shell
   python echo_client.py
   ```

You should see the client sending messages and the service responding to them.

## Troubleshooting

### Connection Issues

If you encounter connection issues:

1. Make sure the NATS server is running:
   ```shell
   docker ps | grep nats
   ```

2. Check if you can connect to the NATS server directly:
   ```shell
   telnet localhost 4222
   ```

3. Verify the NATS URL is correct in your environment:
   ```shell
   echo $NATS_URL
   ```

### Debugging

Both examples include detailed logging. You can adjust the log level by modifying the `logging.basicConfig` call in the scripts:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG for more details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
``` 