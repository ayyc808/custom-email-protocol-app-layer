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
# Tests full round trip: alice sends, bob retrieves
# under 4 different network conditions.

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


def write_send_script(client_dir, server_ip, index):
    # Write alice send script to results dir (accessible inside Mininet)
    script_path = os.path.join(RESULTS_DIR, 'send_client.py')
    with open(script_path, 'w') as f:
        f.write(f"""
import sys
sys.path.insert(0, '{client_dir}')
from utils import connect_to_server, send_command
try:
    s = connect_to_server('{server_ip}', 5000, timeout=15)
    s.recv(4096)
    send_command(s, 'HELLO alice')
    send_command(s, 'AUTH pass123')
    r = send_command(s, 'SEND bob Subject{index} Body of message {index}')
    print(r)
    send_command(s, 'QUIT')
    s.close()
except Exception as e:
    print('ERROR', e)
""")
    return script_path


def write_retrieve_script(client_dir, server_ip):
    # Write bob retrieve script to results dir (accessible inside Mininet)
    script_path = os.path.join(RESULTS_DIR, 'retrieve_client.py')
    with open(script_path, 'w') as f:
        f.write(f"""
import sys
sys.path.insert(0, '{client_dir}')
from utils import connect_to_server, send_command
try:
    s = connect_to_server('{server_ip}', 5000, timeout=15)
    s.recv(4096)
    send_command(s, 'HELLO bob')
    send_command(s, 'AUTH pass456')
    list_resp = send_command(s, 'LIST')
    lines = list_resp.split()
    msg_id = None
    for word in lines:
        if word.startswith('ID:'):
            msg_id = word.replace('ID:', '')
            break
    if msg_id:
        r = send_command(s, f'RETRIEVE {{msg_id}}')
        print(r)
    else:
        print('NO_MESSAGES')
    send_command(s, 'QUIT')
    s.close()
except Exception as e:
    print('ERROR', e)
""")
    return script_path


def run_test(delay_ms, loss_pct, label):
    print(f"\n--- Condition: {label} (delay={delay_ms}ms, loss={loss_pct}%) ---")

    from mininet.node import Controller, OVSSwitch
    net = Mininet(link=TCLink, controller=Controller, switch=OVSSwitch)

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
    time.sleep(4)

    # Verify connectivity before running tests
    ping_result = h2.cmd(f'ping -c 1 -W 2 {server_ip}')
    if '1 received' not in ping_result:
        print(f"  WARNING: h2 cannot reach h1 at {server_ip}")
        print(f"  Ping result: {ping_result.strip()}")
        net.stop()
        return None

    print(f"  Connectivity verified: h2 can reach h1 at {server_ip}")

    send_latencies = []
    retrieve_latencies = []
    roundtrip_latencies = []
    send_failures = 0
    retrieve_failures = 0

    # Run 10 round trip tests
    for i in range(10):
        print(f"  Round {i+1}/10...")

        # ---- ALICE SENDS ----
        send_start = time.time()

        # Write send script to results dir and run it
        send_script = write_send_script(CLIENT_DIR, server_ip, i)
        send_result = h2.cmd(f'python3 {send_script}')

        send_end = time.time()
        send_latency = round((send_end - send_start) * 1000, 2)

        if '201' in send_result:
            send_latencies.append(send_latency)
        else:
            send_failures += 1
            print(f"    Send failed: {send_result.strip()}")
            continue

        # ---- BOB RETRIEVES ----
        retrieve_start = time.time()

        # Write retrieve script to results dir and run it
        retrieve_script = write_retrieve_script(CLIENT_DIR, server_ip)
        retrieve_result = h2.cmd(f'python3 {retrieve_script}')

        retrieve_end = time.time()
        retrieve_latency = round((retrieve_end - retrieve_start) * 1000, 2)

        if '202' in retrieve_result:
            retrieve_latencies.append(retrieve_latency)
            roundtrip = round(send_latency + retrieve_latency, 2)
            roundtrip_latencies.append(roundtrip)
        else:
            retrieve_failures += 1
            print(f"    Retrieve failed: {retrieve_result.strip()}")

    # Calculate metrics
    total = 10
    avg_send = round(sum(send_latencies) / len(send_latencies), 2) if send_latencies else 0
    avg_retrieve = round(sum(retrieve_latencies) / len(retrieve_latencies), 2) if retrieve_latencies else 0
    avg_roundtrip = round(sum(roundtrip_latencies) / len(roundtrip_latencies), 2) if roundtrip_latencies else 0
    send_failure_rate = round((send_failures / total) * 100, 1)
    retrieve_failure_rate = round((retrieve_failures / total) * 100, 1)
    throughput = round(len(send_latencies) / max(sum(send_latencies) / 1000, 0.001), 2)

    print(f"\n  --- Results for {label} ---")
    print(f"  Send successes:       {len(send_latencies)}/10")
    print(f"  Send failures:        {send_failures}/10")
    print(f"  Send failure rate:    {send_failure_rate}%")
    print(f"  Avg send latency:     {avg_send} ms")
    print()
    print(f"  Retrieve successes:   {len(retrieve_latencies)}/10")
    print(f"  Retrieve failures:    {retrieve_failures}/10")
    print(f"  Retrieve failure rate:{retrieve_failure_rate}%")
    print(f"  Avg retrieve latency: {avg_retrieve} ms")
    print()
    print(f"  Avg round trip:       {avg_roundtrip} ms")
    print(f"  Throughput:           {throughput} msg/sec")

    # Save results to JSON
    results = {
        'condition': label,
        'delay_ms': delay_ms,
        'loss_pct': loss_pct,
        'send_successes': len(send_latencies),
        'send_failures': send_failures,
        'send_failure_rate': send_failure_rate,
        'avg_send_latency': avg_send,
        'retrieve_successes': len(retrieve_latencies),
        'retrieve_failures': retrieve_failures,
        'retrieve_failure_rate': retrieve_failure_rate,
        'avg_retrieve_latency': avg_retrieve,
        'avg_roundtrip': avg_roundtrip,
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
        if result:
            all_results.append(result)

    if not all_results:
        print("No results collected. Check connectivity issues above.")
        return

    # Print full summary table
    print("\n" + "=" * 70)
    print("   Full Round Trip Results Summary")
    print("=" * 70)
    print(f"{'Condition':<12} {'Delay':<8} {'Loss':<6} {'Send ms':<10} {'Recv ms':<10} {'RT ms':<10} {'msg/sec'}")
    print("-" * 70)
    for r in all_results:
        print(
            f"{r['condition']:<12} "
            f"{str(r['delay_ms'])+'ms':<8} "
            f"{str(r['loss_pct'])+'%':<6} "
            f"{r['avg_send_latency']:<10} "
            f"{r['avg_retrieve_latency']:<10} "
            f"{r['avg_roundtrip']:<10} "
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

sudo mn -c > /dev/null 2>&1
sudo python3 "$MININET_SCRIPT"

echo ""
echo "=================================================="
echo "Tests complete. Results will get saved in: $RESULTS_DIR"
echo "Then stop Wireshark capture and save the .pcapng file"
echo "=================================================="