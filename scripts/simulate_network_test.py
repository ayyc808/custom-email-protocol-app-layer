#!/usr/bin/env python3
# Network Condition Simulation Test
# Simulates 4 network conditions without Mininet.
# Uses real TCP connections with artificial delay and packet loss.
# Run from project root: python3 scripts/simulate_network_test.py

import sys
import os
import time
import json
import random
import socket
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'client'))

from database import DatabaseManager
from server import EmailServer
from utils import connect_to_server, send_command

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'mininet_results')
os.makedirs(RESULTS_DIR, exist_ok=True)

SERVER_PORT = 5030


def setup_server():
    # Start server with test database
    db = DatabaseManager(os.path.join(
        os.path.dirname(__file__), '..', 'server', 'sim_test.db'
    ))
    db.create_user('alice', 'pass123')
    db.create_user('bob', 'pass456')

    server = EmailServer(
        host='localhost',
        port=SERVER_PORT,
        db=db,
        timeout=30
    )
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    time.sleep(1)
    return server, db


def simulate_send(delay_ms, loss_pct, index):
    # Simulate network delay
    time.sleep(delay_ms / 1000.0)

    # Simulate packet loss
    if random.random() < (loss_pct / 100.0):
        return None, 0

    start = time.time()
    try:
        s = connect_to_server('localhost', SERVER_PORT, timeout=15)
        s.recv(4096)
        send_command(s, 'HELLO alice')
        send_command(s, 'AUTH pass123')

        # Simulate delay mid-connection
        time.sleep(delay_ms / 1000.0)

        r = send_command(s, f'SEND bob Subject{index} Body of message {index}')
        send_command(s, 'QUIT')
        s.close()

        latency = round((time.time() - start) * 1000 + delay_ms, 2)
        return r, latency
    except Exception as e:
        return None, 0


def simulate_retrieve(delay_ms, loss_pct):
    # Simulate network delay
    time.sleep(delay_ms / 1000.0)

    # Simulate packet loss
    if random.random() < (loss_pct / 100.0):
        return None, 0

    start = time.time()
    try:
        s = connect_to_server('localhost', SERVER_PORT, timeout=15)
        s.recv(4096)
        send_command(s, 'HELLO bob')
        send_command(s, 'AUTH pass456')

        # Simulate delay mid-connection
        time.sleep(delay_ms / 1000.0)

        list_resp = send_command(s, 'LIST')
        lines = list_resp.split()
        msg_id = None
        for word in lines:
            if word.startswith('ID:'):
                msg_id = word.replace('ID:', '')
                break

        if msg_id:
            r = send_command(s, f'RETRIEVE {msg_id}')
            send_command(s, 'QUIT')
            s.close()
            latency = round((time.time() - start) * 1000 + delay_ms, 2)
            return r, latency
        else:
            s.close()
            return None, 0
    except Exception as e:
        return None, 0


def run_condition(delay_ms, loss_pct, label):
    print(f"\n--- Condition: {label} (delay={delay_ms}ms, loss={loss_pct}%) ---")

    send_latencies = []
    retrieve_latencies = []
    roundtrip_latencies = []
    send_failures = 0
    retrieve_failures = 0

    for i in range(10):
        print(f"  Round {i+1}/10...")

        # Alice sends
        send_result, send_latency = simulate_send(delay_ms, loss_pct, i)

        if send_result and '201' in send_result:
            send_latencies.append(send_latency)
        else:
            send_failures += 1
            print(f"    Send failed (simulated loss or error)")
            continue

        # Bob retrieves
        retrieve_result, retrieve_latency = simulate_retrieve(delay_ms, loss_pct)

        if retrieve_result and '202' in retrieve_result:
            retrieve_latencies.append(retrieve_latency)
            roundtrip_latencies.append(round(send_latency + retrieve_latency, 2))
        else:
            retrieve_failures += 1
            print(f"    Retrieve failed (simulated loss or error)")

    # Calculate metrics
    total = 10
    avg_send = round(sum(send_latencies) / len(send_latencies), 2) if send_latencies else 0
    avg_retrieve = round(sum(retrieve_latencies) / len(retrieve_latencies), 2) if retrieve_latencies else 0
    avg_roundtrip = round(sum(roundtrip_latencies) / len(roundtrip_latencies), 2) if roundtrip_latencies else 0
    send_failure_rate = round((send_failures / total) * 100, 1)
    retrieve_failure_rate = round((retrieve_failures / total) * 100, 1)
    throughput = round(len(send_latencies) / max(sum(send_latencies) / 1000, 0.001), 2)

    print(f"\n  --- Results for {label} ---")
    print(f"  Send successes:        {len(send_latencies)}/10")
    print(f"  Send failures:         {send_failures}/10")
    print(f"  Send failure rate:     {send_failure_rate}%")
    print(f"  Avg send latency:      {avg_send} ms")
    print()
    print(f"  Retrieve successes:    {len(retrieve_latencies)}/10")
    print(f"  Retrieve failures:     {retrieve_failures}/10")
    print(f"  Retrieve failure rate: {retrieve_failure_rate}%")
    print(f"  Avg retrieve latency:  {avg_retrieve} ms")
    print()
    print(f"  Avg round trip:        {avg_roundtrip} ms")
    print(f"  Throughput:            {throughput} msg/sec")

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

    return results


def main():
    print("================================================")
    print("   Network Condition Simulation Test")
    print("   Custom Email Protocol - CMPE 148")
    print("================================================")
    print("Starting server...")

    server, db = setup_server()
    print("Server ready on localhost:5030")

    conditions = [
        (0,   0,  'Baseline'),
        (50,  1,  'Moderate'),
        (150, 5,  'Poor'),
        (300, 10, 'Severe'),
    ]

    all_results = []
    for delay, loss, label in conditions:
        result = run_condition(delay, loss, label)
        all_results.append(result)
        time.sleep(1)

    # Print summary table
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

    summary_file = os.path.join(RESULTS_DIR, 'summary.json')
    with open(summary_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull summary saved: {summary_file}")

    # Cleanup
    server.stop()
    db_path = os.path.join(
        os.path.dirname(__file__), '..', 'server', 'sim_test.db'
    )
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists('server.log'):
        os.remove('server.log')

    print("\nSimulation complete.")


if __name__ == '__main__':
    main()