# Load Testing Module
# Tests server performance under concurrent client connections.

import sys
import os
import socket
import threading
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from database import DatabaseManager
from server import EmailServer


def run_client(host, port, username, password, results, index):
    # Single client worker - connects, sends a message, lists inbox, disconnects.
    start_time = time.time()
    success = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((host, port))
        s.recv(4096)  # greeting

        s.send(f'HELLO {username}\r\n'.encode())
        time.sleep(0.05)
        s.recv(4096)

        s.send(f'AUTH {password}\r\n'.encode())
        time.sleep(0.05)
        s.recv(4096)

        s.send(f'SEND bob Subject{index} Body{index}\r\n'.encode())
        time.sleep(0.05)
        resp = s.recv(4096).decode()
        if '201' in resp:
            success = True

        s.send(b'LIST\r\n')
        time.sleep(0.05)
        s.recv(4096)

        s.send(b'QUIT\r\n')
        time.sleep(0.05)
        s.recv(4096)
        s.close()

    except Exception as e:
        pass

    end_time = time.time()
    results[index] = {
        'success': success,
        'latency': round((end_time - start_time) * 1000, 2)
    }


def run_load_test(num_clients, host, port, db):
    # Run a load test with num_clients concurrent connections.
    print(f"\n--- Load Test: {num_clients} concurrent clients ---")

    results = [None] * num_clients
    threads = []

    start = time.time()

    for i in range(num_clients):
        t = threading.Thread(
            target=run_client,
            args=(host, port, 'alice', 'pass123', results, i)
        )
        threads.append(t)

    # Start all threads at once
    for t in threads:
        t.start()

    # Wait for all to finish
    for t in threads:
        t.join(timeout=15)

    end = time.time()

    # Calculate metrics
    total_time = round((end - start) * 1000, 2)
    successes = sum(1 for r in results if r and r['success'])
    failures = num_clients - successes
    failure_rate = round((failures / num_clients) * 100, 1)
    latencies = [r['latency'] for r in results if r]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0
    throughput = round(successes / (end - start), 2) if (end - start) > 0 else 0

    print(f"  Clients:      {num_clients}")
    print(f"  Successes:    {successes}")
    print(f"  Failures:     {failures}")
    print(f"  Failure rate: {failure_rate}%")
    print(f"  Avg latency:  {avg_latency} ms")
    print(f"  Throughput:   {throughput} msg/sec")
    print(f"  Total time:   {total_time} ms")

    return {
        'clients': num_clients,
        'successes': successes,
        'failures': failures,
        'failure_rate': failure_rate,
        'avg_latency': avg_latency,
        'throughput': throughput,
        'total_time': total_time
    }


def main():
    # Setup server for load testing.
    import tempfile
    tmp = tempfile.mkdtemp()
    db = DatabaseManager(os.path.join(tmp, 'load_test.db'))
    db.create_user('alice', 'pass123')
    db.create_user('bob', 'pass456')

    server = EmailServer(host='localhost', port=5020, db=db,
                         max_connections=50, timeout=30)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    time.sleep(0.5)

    print("=" * 50)
    print("   Load Test - Custom Email Protocol Server")
    print("=" * 50)

    all_results = []
    for count in [5, 10, 25, 50]:
        result = run_load_test(count, 'localhost', 5020, db)
        all_results.append(result)
        time.sleep(1)  # brief pause between test runs

    print("\n" + "=" * 50)
    print("   Summary Table")
    print("=" * 50)
    print(f"{'Clients':<10} {'Success':<10} {'Fail%':<10} {'Avg ms':<12} {'msg/sec':<10}")
    print("-" * 50)
    for r in all_results:
        print(f"{r['clients']:<10} {r['successes']:<10} {r['failure_rate']:<10} {r['avg_latency']:<12} {r['throughput']:<10}")

    server.stop()
    print("\nLoad test complete.")


if __name__ == "__main__":
    main()