# Client Utilities
# Helper functions for the CLI client.

import socket
import json
import os


def load_config(config_path: str = None) -> dict:
    # Load client config from JSON file.
    # Returns config dictionary.
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'client_config.json'
        )
    with open(config_path) as f:
        return json.load(f)


def connect_to_server(host: str, port: int, timeout: int = 60) -> socket.socket:
    # Create a TCP connection to the server.
    # Returns connected socket.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    return s


def send_command(sock: socket.socket, command: str) -> str:
    # Send a command to the server and receive the response.
    # Returns the full response string.
    sock.send((command + '\r\n').encode('utf-8'))
    return receive_response(sock)


def receive_response(sock: socket.socket, buffer_size: int = 4096) -> str:
    # Receive a response from the server.
    # Handles multi-line responses ending with a period on its own line.
    response = ''
    while True:
        chunk = sock.recv(buffer_size).decode('utf-8', errors='ignore')
        response += chunk

        # Check if this is a complete single-line response
        if response.endswith('\r\n') and '\r\n.\r\n' not in response:
            lines = response.strip().split('\r\n')
            # If only one line or last line is not a continuation
            if len(lines) == 1 or not response.startswith('200') and not response.startswith('202'):
                break

        # Multi-line response ends with a period on its own line
        if response.endswith('\r\n.\r\n') or response.endswith('\n.\n'):
            break

        # Single line responses - break after first chunk
        if chunk.endswith('\r\n') and not chunk.startswith('200 OK\r\n') or len(chunk) < buffer_size:
            break

    return response.strip()


def format_message_list(response: str) -> str:
    # Format the LIST response for display.
    lines = response.split('\r\n')
    if not lines:
        return "No messages"

    output = []
    for line in lines:
        if line == '.':
            continue
        output.append(line)
    return '\n'.join(output)


def format_message(response: str) -> str:
    # Format a RETRIEVE response for display.
    lines = response.split('\r\n')
    output = []
    for line in lines:
        if line == '.':
            continue
        output.append(line)
    return '\n'.join(output)


def print_banner():
    # Print the client welcome banner.
    print("=" * 50)
    print("   Custom Email Protocol Client")
    print("   CMPE 148 - Computer Networks I")
    print("=" * 50)


def print_help():
    # Print available commands.
    print("\nAvailable commands:")
    print("  SEND <to> <subject> <body>  - Send a message")
    print("  LIST                        - List your messages")
    print("  RETRIEVE <id>               - Read a message")
    print("  DELETE <id>                 - Delete a message")
    print("  QUIT                        - Exit the client")
    print("  HELP                        - Show this help\n")