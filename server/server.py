# Server Implementation
# Multi-threaded email server that handles client connections,
# processes protocol commands, and manages message storage.

import socket
import threading
import logging
import json
import os
import sys

logger = logging.getLogger(__name__)


class EmailServer:
    # Multi-threaded email server implementing custom protocol.

    def __init__(self, host: str = 'localhost', port: int = 5000,
                 db=None, max_connections: int = 50, timeout: int = 300):
        self.host = host
        self.port = port
        self.db = db
        self.max_connections = max_connections
        self.timeout = timeout
        self.server_socket = None
        self.running = False
        self.clients = {}
        self.clients_lock = threading.Lock()

    def start(self):
        # Start the server and begin accepting connections.
        logger.info(f"Server starting on {self.host}:{self.port}")

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True

            logger.info(f"Server listening on {self.host}:{self.port}")

            while self.running:
                # Check for new connections every second
                self.server_socket.settimeout(1.0)
                try:
                    client_socket, address = self.server_socket.accept()
                except socket.timeout:
                    continue

                # Reject if at max connections
                with self.clients_lock:
                    if len(self.clients) >= self.max_connections:
                        logger.warning(f"Max connections reached, rejecting {address}")
                        client_socket.send(b"500 Server busy, try again later\r\n")
                        client_socket.close()
                        continue

                logger.info(f"Accepted connection from {address}")

                # Spawn a thread per client
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()

        except OSError as e:
            logger.error(f"Server error: {e}")
        finally:
            self.stop()

    def handle_client(self, client_socket: socket.socket, address: tuple):
        # Handle an individual client connection in its own thread.
        from protocol_handler import ProtocolHandler

        client_key = f"{address[0]}:{address[1]}"
        client_socket.settimeout(self.timeout)

        # Register client
        with self.clients_lock:
            self.clients[client_key] = (client_socket, address)

        logger.info(f"New client connected: {address}")

        # Each client gets its own protocol handler and state machine
        handler = ProtocolHandler(self.db)

        try:
            # Send greeting
            client_socket.send(b"200 OK Custom Email Protocol Server Ready\r\n")

            while not handler.is_closed():
                try:
                    data = client_socket.recv(4096)
                except socket.timeout:
                    logger.warning(f"Client {address} timed out")
                    break

                if not data:
                    logger.info(f"Client {address} disconnected")
                    break

                # Process each line in the received data
                raw = data.decode('utf-8', errors='ignore')
                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    logger.debug(f"[{address}] CMD: {line}")
                    response = handler.process_command(line)
                    logger.debug(f"[{address}] RSP: {response}")

                    client_socket.send((response + "\r\n").encode('utf-8'))

                    if handler.is_closed():
                        break

        except ConnectionResetError:
            logger.warning(f"Client {address} reset connection")
        except Exception as e:
            logger.error(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            with self.clients_lock:
                self.clients.pop(client_key, None)
            logger.info(f"Client disconnected: {address} | Active: {len(self.clients)}")

    def stop(self):
        # Stop the server and close all active connections.
        logger.info("Stopping server...")
        self.running = False

        with self.clients_lock:
            for client_key, (client_socket, address) in list(self.clients.items()):
                try:
                    client_socket.send(b"500 Server shutting down\r\n")
                    client_socket.close()
                except Exception:
                    pass
            self.clients.clear()

        if self.server_socket:
            self.server_socket.close()

        logger.info("Server stopped")


def main():
    # Load config, initialize database, and start server.
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'server_config.json')

    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: server_config.json not found")
        sys.exit(1)

    # Setup logging
    log_level = getattr(logging, config['logging']['level'], logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config['logging']['file']),
            logging.StreamHandler()
        ]
    )

    # Initialize database
    from database import DatabaseManager
    db = DatabaseManager(config['database']['path'])
    logger.info("Database initialized")

    # Start server
    server = EmailServer(
        host=config['server']['host'],
        port=config['server']['port'],
        db=db,
        max_connections=config['server']['max_connections'],
        timeout=config['server']['timeout']
    )

    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        server.stop()


if __name__ == "__main__":
    main()