# Server Integration Tests
# Tests for the multi-threaded server and client connections.

import pytest
import sys
import os
import socket
import threading
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from database import DatabaseManager
from server import EmailServer


@pytest.fixture(scope='module')
def server_setup(tmp_path_factory):
    # Start a server once for all tests in this module.
    tmp_path = tmp_path_factory.mktemp('data')
    db = DatabaseManager(str(tmp_path / 'test.db'))
    db.create_user('alice', 'pass123')
    db.create_user('bob', 'pass456')
    db.store_message('alice', 'bob', 'Hello', 'Test body')

    server = EmailServer(host='localhost', port=5010, db=db, timeout=5)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    time.sleep(0.5)

    yield server, db

    server.stop()


def make_connection(port=5010):
    # Helper to create a connected socket and read greeting.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect(('localhost', port))
    greeting = s.recv(4096).decode().strip()
    return s, greeting


def send_cmd(sock, cmd):
    # Helper to send a command and get response.
    sock.send((cmd + '\r\n').encode())
    time.sleep(0.1)
    return sock.recv(4096).decode().strip()


# ==================== CONNECTION TESTS ====================

class TestConnection:

    def test_server_greeting(self, server_setup):
        s, greeting = make_connection()
        assert '200' in greeting
        s.close()

    def test_multiple_connections(self, server_setup):
        # Open 3 connections simultaneously
        connections = []
        for _ in range(3):
            s, greeting = make_connection()
            assert '200' in greeting
            connections.append(s)
        for s in connections:
            s.close()

    def test_quit_closes_connection(self, server_setup):
        s, _ = make_connection()
        send_cmd(s, 'HELLO alice')
        send_cmd(s, 'AUTH pass123')
        response = send_cmd(s, 'QUIT')
        assert '200' in response
        s.close()


# ==================== FULL FLOW TESTS ====================

class TestFullFlow:

    def test_send_and_receive(self, server_setup):
        # Alice sends a message to bob
        s1, _ = make_connection()
        send_cmd(s1, 'HELLO alice')
        send_cmd(s1, 'AUTH pass123')
        response = send_cmd(s1, 'SEND bob Subject1 Body of message')
        assert '201' in response
        s1.close()

        # Bob receives it
        s2, _ = make_connection()
        send_cmd(s2, 'HELLO bob')
        send_cmd(s2, 'AUTH pass456')
        response = send_cmd(s2, 'LIST')
        assert '200' in response
        s2.close()

    def test_retrieve_message(self, server_setup):
        s, _ = make_connection()
        send_cmd(s, 'HELLO bob')
        send_cmd(s, 'AUTH pass456')
        response = send_cmd(s, 'RETRIEVE 1')
        assert '202' in response
        s.close()

    def test_delete_message(self, server_setup):
        # Send a message first
        s1, _ = make_connection()
        send_cmd(s1, 'HELLO alice')
        send_cmd(s1, 'AUTH pass123')
        send_cmd(s1, 'SEND bob DeleteMe Body')
        s1.close()

        # Bob deletes it
        s2, _ = make_connection()
        send_cmd(s2, 'HELLO bob')
        send_cmd(s2, 'AUTH pass456')
        list_resp = send_cmd(s2, 'LIST')
        # Get last message id from list
        lines = list_resp.split('\n')
        msg_line = [l for l in lines if l.startswith('ID:')]
        if msg_line:
            msg_id = msg_line[-1].split()[0].replace('ID:', '')
            response = send_cmd(s2, f'DELETE {msg_id}')
            assert '200' in response
        s2.close()


# ==================== ERROR HANDLING TESTS ====================

class TestErrorHandling:

    def test_invalid_command(self, server_setup):
        s, _ = make_connection()
        response = send_cmd(s, 'INVALID')
        assert '400' in response
        s.close()

    def test_wrong_password(self, server_setup):
        s, _ = make_connection()
        send_cmd(s, 'HELLO alice')
        response = send_cmd(s, 'AUTH wrongpass')
        assert '401' in response
        s.close()

    def test_unknown_user(self, server_setup):
        s, _ = make_connection()
        response = send_cmd(s, 'HELLO ghost')
        assert '400' in response
        s.close()

    def test_send_to_unknown_user(self, server_setup):
        s, _ = make_connection()
        send_cmd(s, 'HELLO alice')
        send_cmd(s, 'AUTH pass123')
        response = send_cmd(s, 'SEND nobody Subject Body')
        assert '404' in response
        s.close()

    def test_retrieve_nonexistent(self, server_setup):
        s, _ = make_connection()
        send_cmd(s, 'HELLO alice')
        send_cmd(s, 'AUTH pass123')
        response = send_cmd(s, 'RETRIEVE 9999')
        assert '404' in response
        s.close()