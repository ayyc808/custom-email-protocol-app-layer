# Protocol Handler Module
# Implements the protocol state machine and command processing logic.

from enum import Enum
from typing import Optional
from auth import validate_credentials


class ClientState(Enum):
    # Client connection states for the protocol state machine.
    CONNECTED = "CONNECTED"
    IDENTIFIED = "IDENTIFIED"
    AUTHENTICATED = "AUTHENTICATED"
    CLOSED = "CLOSED"


class ResponseCode:
    # Protocol response codes.
    OK = "200 OK"
    MESSAGE_SENT = "201 Message Sent"
    MESSAGE_RETRIEVED = "202 Message Retrieved"
    BAD_REQUEST = "400 Bad Request"
    UNAUTHORIZED = "401 Unauthorized"
    NOT_FOUND = "404 Not Found"
    SERVER_ERROR = "500 Server Error"


class ProtocolHandler:
    # Handles protocol command parsing and state machine logic.

    def __init__(self, database_manager):
        self.db = database_manager
        self.state = ClientState.CONNECTED
        self.username: Optional[str] = None
        self.auth_attempts = 0
        self.max_auth_attempts = 3

    def process_command(self, command: str) -> str:
        # Process a client command based on current state.
        command = command.strip()

        if not command:
            return f"{ResponseCode.BAD_REQUEST} Empty command"

        # Split into command and arguments
        parts = command.split(' ', 1)
        cmd = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ""

        # Route to correct state handler
        if self.state == ClientState.CONNECTED:
            return self._handle_connected_state(cmd, args)
        elif self.state == ClientState.IDENTIFIED:
            return self._handle_identified_state(cmd, args)
        elif self.state == ClientState.AUTHENTICATED:
            return self._handle_authenticated_state(cmd, args)
        else:
            return f"{ResponseCode.SERVER_ERROR} Unknown state"

    def _handle_connected_state(self, cmd: str, args: str) -> str:
        # Handle commands in CONNECTED state.
        # Allowed: HELLO, QUIT
        if cmd == "HELLO":
            if not args:
                return f"{ResponseCode.BAD_REQUEST} Missing username"

            username = args.strip()

            # Validate username format
            valid, error = validate_credentials(username, "placeholder")
            if not valid and "Username" in error:
                return f"{ResponseCode.BAD_REQUEST} {error}"

            # Check user exists in database
            if not self.db.user_exists(username):
                return f"{ResponseCode.BAD_REQUEST} Unknown user"

            self.username = username
            self.state = ClientState.IDENTIFIED
            return f"{ResponseCode.OK} Hello {self.username}, please authenticate"

        elif cmd == "QUIT":
            self.state = ClientState.CLOSED
            return "200 Goodbye"

        else:
            return f"{ResponseCode.BAD_REQUEST} Command not allowed in CONNECTED state"

    def _handle_identified_state(self, cmd: str, args: str) -> str:
        # Handle commands in IDENTIFIED state.
        # Allowed: AUTH, QUIT
        if cmd == "AUTH":
            if not args:
                return f"{ResponseCode.BAD_REQUEST} Missing password"

            # Check if too many failed attempts
            if self.auth_attempts >= self.max_auth_attempts:
                self.state = ClientState.CLOSED
                return f"{ResponseCode.UNAUTHORIZED} Too many failed attempts, closing connection"

            password = args.strip()

            if self.db.authenticate_user(self.username, password):
                self.auth_attempts = 0
                self.state = ClientState.AUTHENTICATED
                return f"{ResponseCode.OK} Authenticated as {self.username}"
            else:
                self.auth_attempts += 1
                remaining = self.max_auth_attempts - self.auth_attempts
                if remaining == 0:
                    self.state = ClientState.CLOSED
                    return f"{ResponseCode.UNAUTHORIZED} Too many failed attempts, closing connection"
                return f"{ResponseCode.UNAUTHORIZED} Invalid password, {remaining} attempt(s) remaining"

        elif cmd == "QUIT":
            self.state = ClientState.CLOSED
            return "200 Goodbye"

        else:
            return f"{ResponseCode.BAD_REQUEST} Command not allowed in IDENTIFIED state"

    def _handle_authenticated_state(self, cmd: str, args: str) -> str:
        # Handle commands in AUTHENTICATED state.
        # Allowed: SEND, LIST, RETRIEVE, DELETE, QUIT
        if cmd == "SEND":
            return self._handle_send(args)
        elif cmd == "LIST":
            return self._handle_list()
        elif cmd == "RETRIEVE":
            return self._handle_retrieve(args)
        elif cmd == "DELETE":
            return self._handle_delete(args)
        elif cmd == "QUIT":
            self.state = ClientState.CLOSED
            return "200 Goodbye"
        else:
            return f"{ResponseCode.BAD_REQUEST} Unknown command"

    def _handle_send(self, args: str) -> str:
        # Handle SEND command.
        # Format: SEND <to_user> <subject> <body>
        parts = args.split(' ', 2)
        if len(parts) < 3:
            return f"{ResponseCode.BAD_REQUEST} Usage: SEND <to_user> <subject> <body>"

        to_user, subject, body = parts

        if not self.db.user_exists(to_user):
            return f"{ResponseCode.NOT_FOUND} User '{to_user}' not found"

        if not subject.strip():
            return f"{ResponseCode.BAD_REQUEST} Subject cannot be empty"

        if not body.strip():
            return f"{ResponseCode.BAD_REQUEST} Body cannot be empty"

        message_id = self.db.store_message(
            from_user=self.username,
            to_user=to_user,
            subject=subject,
            body=body
        )

        if message_id:
            return f"{ResponseCode.MESSAGE_SENT} ID:{message_id}"
        else:
            return f"{ResponseCode.SERVER_ERROR} Failed to store message"

    def _handle_list(self) -> str:
        # Handle LIST command.
        # Returns formatted list of messages for current user.
        messages = self.db.get_messages_for_user(self.username)

        if not messages:
            return f"{ResponseCode.OK} 0 messages"

        lines = [f"{ResponseCode.OK} {len(messages)} message(s)"]
        for msg in messages:
            status = "UNREAD" if not msg['read'] else "READ"
            lines.append(
                f"ID:{msg['message_id']} "
                f"FROM:{msg['from_user']} "
                f"SUBJ:{msg['subject']} "
                f"DATE:{msg['timestamp']} "
                f"[{status}]"
            )
        lines.append(".")
        return "\r\n".join(lines)

    def _handle_retrieve(self, args: str) -> str:
        # Handle RETRIEVE command.
        # Format: RETRIEVE <message_id>
        try:
            message_id = int(args.strip())
        except ValueError:
            return f"{ResponseCode.BAD_REQUEST} Message ID must be a number"

        message = self.db.get_message(message_id, self.username)

        if not message:
            return f"{ResponseCode.NOT_FOUND} Message not found"

        response = f"{ResponseCode.MESSAGE_RETRIEVED}\r\n"
        response += f"FROM: {message['from_user']}\r\n"
        response += f"SUBJECT: {message['subject']}\r\n"
        response += f"DATE: {message['timestamp']}\r\n"
        response += f"\r\n{message['body']}\r\n."
        return response

    def _handle_delete(self, args: str) -> str:
        # Handle DELETE command.
        # Format: DELETE <message_id>
        try:
            message_id = int(args.strip())
        except ValueError:
            return f"{ResponseCode.BAD_REQUEST} Message ID must be a number"

        if self.db.delete_message(message_id, self.username):
            return f"{ResponseCode.OK} Message deleted"
        else:
            return f"{ResponseCode.NOT_FOUND} Message not found"

    def is_closed(self) -> bool:
        # Returns True if client has quit or been closed.
        return self.state == ClientState.CLOSED