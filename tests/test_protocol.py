# Protocol Handler Unit Tests
# Tests for the protocol state machine and command processing.

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from database import DatabaseManager
from protocol_handler import ProtocolHandler, ClientState, ResponseCode


@pytest.fixture
def db(tmp_path):
    # Create a temporary database for each test.
    db = DatabaseManager(str(tmp_path / 'test.db'))
    db.create_user('alice', 'pass123')
    db.create_user('bob', 'pass456')
    return db


@pytest.fixture
def handler(db):
    # Create a fresh protocol handler for each test.
    return ProtocolHandler(db)


@pytest.fixture
def auth_handler(db):
    # Create a fully authenticated handler for each test.
    h = ProtocolHandler(db)
    h.process_command('HELLO alice')
    h.process_command('AUTH pass123')
    return h


# ==================== CONNECTED STATE ====================

class TestConnectedState:

    def test_hello_valid_user(self, handler):
        response = handler.process_command('HELLO alice')
        assert '200' in response
        assert handler.state == ClientState.IDENTIFIED

    def test_hello_unknown_user(self, handler):
        response = handler.process_command('HELLO ghost')
        assert '400' in response
        assert handler.state == ClientState.CONNECTED

    def test_hello_no_username(self, handler):
        response = handler.process_command('HELLO')
        assert '400' in response

    def test_hello_invalid_username(self, handler):
        response = handler.process_command('HELLO ali ce')
        assert '400' in response

    def test_quit_from_connected(self, handler):
        response = handler.process_command('QUIT')
        assert '200' in response
        assert handler.is_closed()

    def test_list_not_allowed_in_connected(self, handler):
        response = handler.process_command('LIST')
        assert '400' in response

    def test_send_not_allowed_in_connected(self, handler):
        response = handler.process_command('SEND bob Hi test')
        assert '400' in response


# ==================== IDENTIFIED STATE ====================

class TestIdentifiedState:

    def test_auth_valid(self, handler):
        handler.process_command('HELLO alice')
        response = handler.process_command('AUTH pass123')
        assert '200' in response
        assert handler.state == ClientState.AUTHENTICATED

    def test_auth_invalid(self, handler):
        handler.process_command('HELLO alice')
        response = handler.process_command('AUTH wrongpass')
        assert '401' in response
        assert handler.state == ClientState.IDENTIFIED

    def test_auth_no_password(self, handler):
        handler.process_command('HELLO alice')
        response = handler.process_command('AUTH')
        assert '400' in response

    def test_auth_brute_force_lockout(self, handler):
        handler.process_command('HELLO alice')
        handler.process_command('AUTH wrong1')
        handler.process_command('AUTH wrong2')
        response = handler.process_command('AUTH wrong3')
        assert '401' in response
        assert handler.is_closed()

    def test_quit_from_identified(self, handler):
        handler.process_command('HELLO alice')
        response = handler.process_command('QUIT')
        assert '200' in response
        assert handler.is_closed()

    def test_list_not_allowed_in_identified(self, handler):
        handler.process_command('HELLO alice')
        response = handler.process_command('LIST')
        assert '400' in response


# ==================== AUTHENTICATED STATE ====================

class TestAuthenticatedState:

    def test_send_valid(self, auth_handler):
        response = auth_handler.process_command('SEND bob Hello Test body')
        assert '201' in response
        assert 'ID:' in response

    def test_send_unknown_recipient(self, auth_handler):
        response = auth_handler.process_command('SEND nobody Hello Test')
        assert '404' in response

    def test_send_missing_args(self, auth_handler):
        response = auth_handler.process_command('SEND bob')
        assert '400' in response

    def test_list_empty(self, auth_handler):
        response = auth_handler.process_command('LIST')
        assert '200' in response
        assert '0' in response

    def test_list_with_messages(self, auth_handler, db):
        db.store_message('bob', 'alice', 'Hi', 'Hello there')
        response = auth_handler.process_command('LIST')
        assert '200' in response
        assert '1' in response

    def test_retrieve_valid(self, auth_handler, db):
        db.store_message('bob', 'alice', 'Hi', 'Hello there')
        auth_handler.process_command('LIST')
        msgs = db.get_messages_for_user('alice')
        msg_id = msgs[0]['message_id']
        response = auth_handler.process_command(f'RETRIEVE {msg_id}')
        assert '202' in response
        assert 'Hi' in response

    def test_retrieve_invalid_id(self, auth_handler):
        response = auth_handler.process_command('RETRIEVE abc')
        assert '400' in response

    def test_retrieve_not_found(self, auth_handler):
        response = auth_handler.process_command('RETRIEVE 999')
        assert '404' in response

    def test_delete_valid(self, auth_handler, db):
        db.store_message('bob', 'alice', 'Hi', 'Hello there')
        msgs = db.get_messages_for_user('alice')
        msg_id = msgs[0]['message_id']
        response = auth_handler.process_command(f'DELETE {msg_id}')
        assert '200' in response

    def test_delete_not_found(self, auth_handler):
        response = auth_handler.process_command('DELETE 999')
        assert '404' in response

    def test_delete_invalid_id(self, auth_handler):
        response = auth_handler.process_command('DELETE abc')
        assert '400' in response

    def test_quit_from_authenticated(self, auth_handler):
        response = auth_handler.process_command('QUIT')
        assert '200' in response
        assert auth_handler.is_closed()

    def test_unknown_command(self, auth_handler):
        response = auth_handler.process_command('INVALID')
        assert '400' in response