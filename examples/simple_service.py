#!/usr/bin/env python3
"""
Simple example of using fluxlib to create a service with a node.

This example demonstrates:
1. Creating a service
2. Attaching a NATS transport
3. Creating and adding a node
4. Running the service
5. Publishing and subscribing to messages
"""

import asyncio
import os
import logging
from typing import Dict, Any

from fluxlib.service import Service, ServiceOptions
from fluxlib.node import Node
from fluxmq.adapter.nats import Nats
from fluxmq.topic import Topic
from fluxmq.status import Status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fluxlib-example")

class EchoNode(Node):
    """
    A simple node that echoes messages received on a topic.
    """
    
    async def on_init(self):
        """Called when the node is initialized."""
        logger.info(f"Node {self.id} initialized")
        
        # Subscribe to the echo topic
        await self.service.subscribe_handler(
            f"echo/{self.id}/request", 
            self.handle_echo_request
        )
    
    async def on_start(self):
        """Called when the node is started."""
        logger.info(f"Node {self.id} started")
        
        # Publish a message to indicate the node is ready
        await self.service.publish(
            f"echo/{self.id}/status", 
            {"status": "ready", "message": f"Echo node {self.id} is ready"}
        )
    
    async def on_stop(self):
        """Called when the node is stopped."""
        logger.info(f"Node {self.id} stopped")
        
        # Publish a message to indicate the node is stopping
        await self.service.publish(
            f"echo/{self.id}/status", 
            {"status": "stopped", "message": f"Echo node {self.id} is stopping"}
        )
    
    async def handle_echo_request(self, message: Dict[str, Any]):
        """
        Handle echo requests by sending back the same message.
        
        Args:
            message: The message to echo back
        """
        logger.info(f"Received echo request: {message}")
        
        # Echo the message back on the response topic
        await self.service.publish(
            f"echo/{self.id}/response", 
            {
                "original_message": message,
                "echo": message,
                "node_id": self.id
            }
        )

async def main():
    """Main function to run the example."""
    # Get NATS URL from environment or use default
    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    
    # Create a service
    service = Service(service_id="echo-service")
    
    # Create and configure the NATS transport
    transport = Nats()
    
    try:
        # Connect to NATS
        logger.info(f"Connecting to NATS server at {nats_url}")
        await transport.connect(nats_url)
        
        # Attach transport to service
        service.attach(transport, Topic(), Status())
        
        # Create and add the echo node
        echo_node = EchoNode(node_id="echo1", service=service)
        service.append_node(echo_node)
        
        # Run the service
        logger.info("Starting echo service")
        await service.run()
        
        # Start the node
        await service.start_node("echo1")
        
        # Keep the service running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        # Stop the node
        await service.stop_node("echo1")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        # Clean up
        if transport and hasattr(transport, 'close'):
            await transport.close()

if __name__ == "__main__":
    asyncio.run(main()) 