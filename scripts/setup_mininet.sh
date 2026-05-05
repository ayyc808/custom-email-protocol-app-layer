#!/bin/bash
# Mininet Network Testing Script
# Tests the custom email protocol under various network conditions.
# For using it: sudo bash setup_mininet.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_DIR="$PROJECT_DIR/server"
CLIENT_DIR="$PROJECT_DIR/client"
RESULTS_DIR="$PROJECT_DIR/mininet_results"

mkdir -p "$RESULTS_DIR"

echo "=================================================="
echo "   Custom Email Protocol - Mininet Network Tests"
echo "=================================================="
echo "Project directory: $PROJECT_DIR"

# Check Mininet is installed
if ! command -v mn &> /dev/null; then
    echo "ERROR: Mininet not found. Install with:"
    echo "  sudo apt-get install mininet"
    exit 1
fi

# Check Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found."
    exit 1
fi

# Seed the database with test users
echo ""
echo "Setting up test database..."
cd "$SERVER_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
from database import DatabaseManager
db = DatabaseManager('email_server.db')
db.create_user('alice', 'pass123')
db.create_user('bob', 'pass456')
print('Test users created: alice, bob')
"

# Write the Mininet Python test script
MININET_SCRIPT="$PROJECT_DIR/scripts/run_mininet_test.py"

cat > "$MININET_SCRIPT" << PYEOF
# Mininet Test Runner
# Runs server and client on emulated hosts under different network conditions.

import sys
import os
import time
import json
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel

setLogLevel('warning')

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SERVER_DIR = os.path.join(PROJECT_DIR, 'server')
CLIENT_DIR = os.path.join(PROJECT_DIR, 'client')
RESULTS_DIR = os.path.join(PROJECT_DIR, 'mininet_results')


def run_test(delay_ms, loss_pct, label):
    print(f"\n--- Condition: {label} (delay={delay_ms}ms, loss={loss_pct}%) ---")

    net = Mininet(link=TCLink)

    # h1 = server host, h2 = client host
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    s1 = net.addSwitch('s1')

    # Apply network conditions to both links
    net.addLink(h1, s1, delay=f'{delay_ms}ms', loss=loss_pct)
    net.addLink(h2, s1, delay=f'{delay_ms}ms', loss=loss_pct)

    net.start()

    server_ip = h1.IP()

    # Kill any leftover server processes from previous test
    h1.cmd('pkill -f server.py 2>/dev/null')
    time.sleep(1)

    # Start fresh server on h1
    h1.cmd(f'cd {SERVER_DIR} && python3 server.py &')
    time.sleep(2)

    successes = 0
    failures = 0
    latencies = []

    # Run 10 client sessions
    for i in range(10):
        start = time.time()

        result = h2.cmd(f'python3 -c "
import sys, socket, time
sys.path.insert(0, \\"{CLIENT_DIR}\\")
from utils import connect_to_server, send_command
try:
    s = connect_to_server(\\"{server_ip}\\", 5000, timeout=15)
    s.recv(4096)
    send_command(s, \\"HELLO alice\\")
    send_command(s, \\"AUTH pass123\\")
    r = send_command(s, \\"SEND bob Subject Body\\")
    print(r)
    send_command(s, \\"QUIT\\")
    s.close()
except Exception as e:
    print(\\"ERROR\\", e)
"')

        end = time.time()
        latency_ms = round((end - start) * 1000, 2)

        if '201' in result:
            successes += 1
            latencies.append(latency_ms)
        else:
            failures += 1

    # Calculate metrics
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0
    failure_rate = round((failures / 10) * 100, 1)
    throughput = round(successes / max(sum(latencies) / 1000, 0.001), 2)

    print(f"  Successes:    {successes}/10")
    print(f"  Failures:     {failures}/10")
    print(f"  Failure rate: {failure_rate}%")
    print(f"  Avg latency:  {avg_latency} ms")
    print(f"  Throughput:   {throughput} msg/sec")

    # Save results to JSON
    results = {
        'condition': label,
        'delay_ms': delay_ms,
        'loss_pct': loss_pct,
        'successes': successes,
        'failures': failures,
        'failure_rate': failure_rate,
        'avg_latency': avg_latency,
        'throughput': throughput
    }

    result_file = os.path.join(RESULTS_DIR, f'results_{label.lower()}.json')
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  Saved: {result_file}")

    net.stop()

    # Clean up Mininet state between tests
    os.system('sudo mn -c > /dev/null 2>&1')
    time.sleep(2)

    return results


def main():
    # Four network conditions from the project proposal
    conditions = [
        (0,   0,  'Baseline'),
        (50,  1,  'Moderate'),
        (150, 5,  'Poor'),
        (300, 10, 'Severe'),
    ]

    all_results = []
    for delay, loss, label in conditions:
        result = run_test(delay, loss, label)
        all_results.append(result)

    # Print summary table
    print("\n" + "=" * 60)
    print("   Results Summary")
    print("=" * 60)
    print(f"{'Condition':<12} {'Delay':<10} {'Loss':<8} {'Fail%':<8} {'Avg ms':<12} {'msg/sec'}")
    print("-" * 60)
    for r in all_results:
        print(
            f"{r['condition']:<12} "
            f"{str(r['delay_ms'])+'ms':<10} "
            f"{str(r['loss_pct'])+'%':<8} "
            f"{str(r['failure_rate'])+'%':<8} "
            f"{r['avg_latency']:<12} "
            f"{r['throughput']}"
        )

    # Save full summary
    summary_file = os.path.join(RESULTS_DIR, 'summary.json')
    with open(summary_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull summary saved: {summary_file}")


if __name__ == '__main__':
    main()
PYEOF

echo ""
echo "Starting Mininet tests..."
echo "NOTE: Open Wireshark now and start capturing on 'any' interface"
echo "      with filter: tcp port 5000"
echo ""
read -p "Press Enter when Wireshark is capturing..."

sudo python3 "$MININET_SCRIPT"

echo ""
echo "=================================================="
echo "Tests complete. Results saved in: $RESULTS_DIR"
echo "Then stop Wireshark capture and save the .pcapng file"
echo "=================================================="