# Custom Email Protocol - Application Layer

A custom application layer protocol for email messaging built over TCP sockets, featuring a multi-threaded server, CLI client, SQLite storage, and network performance analysis.

## Team

**TheTechs**
- Alvin Cheng
- Elijah Canonigo

**Course**: CMPE 148 - Computer Networks I

---

## Overview

This project implements a simplified email messaging system from scratch with a custom application layer protocol. The protocol defines its own command set, response codes, and state machine running on top of TCP — similar in concept to how SMTP and POP3 work, but fully custom built.

**Key features:**
- Custom protocol commands: HELLO, AUTH, SEND, LIST, RETRIEVE, DELETE, QUIT
- Response codes: 200 OK, 201 Message Sent, 202 Message Retrieved, 400/401/404/500
- State machine: CONNECTED → IDENTIFIED → AUTHENTICATED
- Multi-threaded server handling up to 50 concurrent clients
- SQLite database with thread-safe mutex locks
- bcrypt password hashing
- Full CLI client

---

## Project Structure
```
custom-email-protocol-app-layer/
├── server/
│   ├── server.py              # Multi-threaded TCP server
│   ├── database.py            # SQLite database operations
│   ├── protocol_handler.py    # Protocol state machine
│   └── auth.py                # bcrypt authentication
├── client/
│   ├── client.py              # CLI client
│   └── utils.py               # Helper functions
├── tests/
│   ├── test_protocol.py       # 26 protocol unit tests
│   ├── test_server.py         # 11 server integration tests
│   └── load_test.py           # Multi-client load testing
├── config/
│   ├── server_config.json     # Server configuration
│   └── client_config.json     # Client configuration
├── scripts/
│   ├── setup_mininet.sh       # Mininet network testing script
│   └── simulate_network_test.py  # Network simulation (WSL compatible)
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.x
- Git

### Step 1 — Clone the repository
```bash
git clone https://github.com/ayyc808/custom-email-protocol-app-layer.git
cd custom-email-protocol-app-layer
```

### Step 2 — Create a virtual environment

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Verify installation
```bash
python3 -c "import bcrypt; print('bcrypt OK')"
python3 -c "import pytest; print('pytest OK')"
```

---

## Running the Application

### Step 1 — Seed the database with users

**Mac/Linux:**
```bash
python3 -c "
import sys
sys.path.insert(0, 'server')
from database import DatabaseManager
db = DatabaseManager('server/email_server.db')
db.create_user('alice', 'pass123')
db.create_user('bob', 'pass456')
db.create_user('charlie', 'pass789')
db.create_user('diana', 'pass101')
db.create_user('evan', 'pass202')
print('All users created')
"
```

**Windows:**
```bash
python -c "import sys; sys.path.insert(0, 'server'); from database import DatabaseManager; db = DatabaseManager('server/email_server.db'); db.create_user('alice', 'pass123'); db.create_user('bob', 'pass456'); db.create_user('charlie', 'pass789'); db.create_user('diana', 'pass101'); db.create_user('evan', 'pass202'); print('All users created')"
```

### Step 2 — Start the server

Open **Terminal 1** and run:

**Mac/Linux:**
```bash
cd server
python3 server.py
```

**Windows:**
```bash
cd server
python server.py
```

You should see:
```
INFO - Database initialized
INFO - Server starting on localhost:5000
INFO - Server listening on localhost:5000
```

### Step 3 — Connect a client

Open **Terminal 2** and run:

**Mac/Linux:**
```bash
cd client
python3 client.py
```

**Windows:**
```bash
cd client
python client.py
```

---

## End to End Demo

### Test Users

| Username | Password |
|----------|----------|
| alice    | pass123  |
| bob      | pass456  |
| charlie  | pass789  |
| diana    | pass101  |
| evan     | pass202  |

### Terminal 2 — Login as alice and send messages - Email format messaging goes as 
### <CMD><USER><SUBJECT_LINE><BODY>
### IF user wants to retrieve a message: <RETRIEVE><Msg_ID_#> 
```
Username: alice
Password: pass123
```
```
SEND bob Hello Hey bob, this is alice!
SEND charlie Greeting Hey charlie, checking in!
LIST
QUIT
```

### Terminal 3 — Login as bob and check inbox

Open a third terminal:

**Mac/Linux:**
```bash
cd client
python3 client.py
```

**Windows:**
```bash
cd client
python client.py
```
```
Username: bob
Password: pass456
```
```
LIST
RETRIEVE 1
DELETE 1
LIST
QUIT
```

### Available Commands

| Command  | Usage                            | Description             |
|----------|----------------------------------|-------------------------|
| SEND     | SEND \<to\> \<subject\> \<body\> | Send a message          |
| LIST     | LIST                             | List your inbox         |
| RETRIEVE | RETRIEVE \<id\>                  | Read a message          |
| DELETE   | DELETE \<id\>                    | Delete a message        |
| HELP     | HELP                             | Show available commands |
| QUIT     | QUIT                             | Exit the client         |

---

## Running the Tests

### Unit and integration tests

**Mac/Linux:**
```bash
pytest tests/test_protocol.py tests/test_server.py -v
```

**Windows:**
```bash
python -m pytest tests/test_protocol.py tests/test_server.py -v
```

Expected: **37 tests passing**

### Load test

**Mac/Linux:**
```bash
python3 tests/load_test.py
```

**Windows:**
```bash
python tests/load_test.py
```

Tests 5, 10, 25, and 50 concurrent clients. Expected: **0% failure rate**.

### Network simulation test

**Mac/Linux:**
```bash
python3 scripts/simulate_network_test.py
```

**Windows:**
```bash
python scripts/simulate_network_test.py
```

Tests protocol performance under 4 network conditions:

| Condition | Delay | Packet Loss |
|-----------|-------|-------------|
| Baseline  | 0ms   | 0%          |
| Moderate  | 50ms  | 1%          |
| Poor      | 150ms | 5%          |
| Severe    | 300ms | 10%         |

---

## Configuration

### Server config — `config/server_config.json`
```json
{
  "server": {
    "host": "localhost",
    "port": 5000,
    "max_connections": 50,
    "timeout": 300
  },
  "database": {
    "path": "email_server.db"
  }
}
```

### Client config — `config/client_config.json`
```json
{
  "server": {
    "host": "localhost",
    "port": 5000
  },
  "client": {
    "timeout": 60,
    "buffer_size": 4096
  }
}
```

---

## Notes

- The virtual environment `venv/` must be activated every time you open a new terminal before running any commands
- The `server/email_server.db` file is ignored by git — you need to seed users once after cloning
- Run the server before connecting any clients
- Multiple clients can connect simultaneously — each gets its own independent session