
# CLI Client
# Command line interface for interacting with the email server.

import socket
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from utils import (load_config, connect_to_server, send_command,
                   format_message_list, format_message,
                   print_banner, print_help)


class EmailClient:
    # CLI client for the custom email protocol.

    def __init__(self, host: str = None, port: int = None):
        # Load config and set connection parameters.
        config = load_config()
        self.host = host or config['server']['host']
        self.port = port or config['server']['port']
        self.timeout = config['client']['timeout']
        self.buffer_size = config['client']['buffer_size']
        self.sock = None
        self.username = None

    def connect(self):
        # Connect to the server and receive greeting.
        try:
            self.sock = connect_to_server(self.host, self.port, self.timeout)
            greeting = self.sock.recv(self.buffer_size).decode('utf-8').strip()
            print(f"Connected: {greeting}")
            return True
        except ConnectionRefusedError:
            print(f"ERROR: Could not connect to {self.host}:{self.port}")
            print("Make sure the server is running.")
            return False
        except Exception as e:
            print(f"ERROR: {e}")
            return False

    def login(self):
        # Handle HELLO and AUTH sequence.
        username = input("Username: ").strip()
        password = input("Password: ").strip()

        # Send HELLO
        response = send_command(self.sock, f"HELLO {username}")
        print(response)
        if not response.startswith("200"):
            return False

        # Send AUTH
        response = send_command(self.sock, f"AUTH {password}")
        print(response)
        if not response.startswith("200"):
            return False

        self.username = username
        return True

    def run(self):
        # Main client loop.
        print_banner()

        if not self.connect():
            sys.exit(1)

        if not self.login():
            print("Login failed. Exiting.")
            self.disconnect()
            sys.exit(1)

        print(f"\nLogged in as {self.username}")
        print("Type HELP for available commands.\n")

        while True:
            try:
                user_input = input(f"[{self.username}]> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                break

            if not user_input:
                continue

            parts = user_input.split(' ', 1)
            cmd = parts[0].upper()
            args = parts[1] if len(parts) > 1 else ""

            if cmd == "HELP":
                print_help()
                continue

            elif cmd == "QUIT":
                response = send_command(self.sock, "QUIT")
                print(response)
                break

            elif cmd == "LIST":
                response = send_command(self.sock, "LIST")
                print(format_message_list(response))

            elif cmd == "RETRIEVE":
                if not args:
                    print("Usage: RETRIEVE <message_id>")
                    continue
                response = send_command(self.sock, f"RETRIEVE {args}")
                print(format_message(response))

            elif cmd == "DELETE":
                if not args:
                    print("Usage: DELETE <message_id>")
                    continue
                response = send_command(self.sock, f"DELETE {args}")
                print(response)

            elif cmd == "SEND":
                if not args:
                    print("Usage: SEND <to> <subject> <body>")
                    continue
                response = send_command(self.sock, f"SEND {args}")
                print(response)

            else:
                print(f"Unknown command: {cmd}. Type HELP for available commands.")

        self.disconnect()

    def disconnect(self):
        # Close the connection to the server.
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        print("Disconnected.")


def main():
    client = EmailClient()
    client.run()


if __name__ == "__main__":
    main()