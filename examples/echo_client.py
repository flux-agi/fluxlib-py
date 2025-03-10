#!/usr/bin/env python3
"""
Echo client example for interacting with the echo service.

This example demonstrates:
1. Connecting to NATS
2. Sending messages to the echo service
3. Receiving responses from the echo service
"""

import asyncio
import os
import json
import logging
import uuid
from typing import Dict, Any

from nats.aio.client import Client as NATS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo-client")

class EchoClient:
    """
    Client for interacting with the echo service.
    """
    
    def __init__(self, nats_url: str = "nats://localhost:4222"):
        """
        Initialize the echo client.
        
        Args:
            nats_url: URL of the NATS server
        """
        self.nats_url = nats_url
        self.nc = NATS()
        self.connected = False
        self.subscription = None
        
    async def connect(self):
        """Connect to the NATS server."""
        try:
            logger.info(f"Connecting to NATS server at {self.nats_url}")
            await self.nc.connect(
                servers=[self.nats_url],
                reconnect_time_wait=2,
                max_reconnect_attempts=10,
                connect_timeout=10
            )
            self.connected = True
            logger.info("Connected to NATS server")
            
            # Subscribe to responses
            self.subscription = await self.nc.subscribe(
                "echo/echo1/response", 
                cb=self.handle_response
            )
            logger.info("Subscribed to echo responses")
            
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {str(e)}")
            raise
    
    async def handle_response(self, msg):
        """
        Handle responses from the echo service.
        
        Args:
            msg: The NATS message
        """
        try:
            data = json.loads(msg.payload.decode())
            logger.info(f"Received response: {data}")
        except Exception as e:
            logger.error(f"Error handling response: {str(e)}")
    
    async def send_echo_request(self, message: Dict[str, Any]):
        """
        Send an echo request to the service.
        
        Args:
            message: The message to echo
        """
        if not self.connected:
            raise RuntimeError("Not connected to NATS server")
        
        try:
            # Add a unique ID to the message
            message["id"] = str(uuid.uuid4())
            
            logger.info(f"Sending echo request: {message}")
            await self.nc.publish(
                "echo/echo1/request", 
                json.dumps(message).encode()
            )
        except Exception as e:
            logger.error(f"Error sending echo request: {str(e)}")
            raise
    
    async def close(self):
        """Close the NATS connection."""
        if self.subscription:
            await self.subscription.unsubscribe()
        
        if self.connected:
            await self.nc.close()
            logger.info("Disconnected from NATS server")

async def main():
    """Main function to run the example."""
    # Get NATS URL from environment or use default
    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    
    # Create and connect the client
    client = EchoClient(nats_url)
    
    try:
        await client.connect()
        
        # Send a few echo requests
        for i in range(5):
            await client.send_echo_request({
                "text": f"Hello, Echo! Message #{i+1}",
                "timestamp": asyncio.get_event_loop().time()
            })
            await asyncio.sleep(1)
        
        # Wait a bit to receive all responses
        logger.info("Waiting for responses...")
        await asyncio.sleep(2)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        # Clean up
        await client.close()

if __name__ == "__main__":
    asyncio.run(main()) 