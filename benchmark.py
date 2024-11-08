import sys
import requests
import time
import random

strategies = ["", "direct", "random", "customized"]

# Generate 1000 write (INSERT) queries
write_queries = [{"query": f"INSERT INTO actor (first_name, last_name) VALUES (\"User{i}\", \"Test{i}\")"} for i in range(1000)]

# Generate 1000 read (SELECT) queries
read_queries = [{"query": f"SELECT * FROM actor WHERE first_name = \"User{i}\";"} for i in range(1000)]

def send_request(request_num, orchestrator_url, query, strategy = ""):
    headers = {"Content-Type": "application/json"}
    if strategy != "":
        query["strategy"] = strategy
    data = query

    try:
        response = requests.post(orchestrator_url, json=data, headers=headers)
        status_code = response.status_code
        response_json = response.json()
        print(f"Request {request_num}: Status Code: {status_code}, Response: {response_json}")
        return status_code, response_json
    except Exception as e:
        print(f"Request {request_num}: Failed - {str(e)}")
        return None, str(e)

def main():
    try:
        with open('gatekeeper_ip.txt', 'r') as file:
            gate_ip = file.read().strip()

        gatekeeper_ip = f"http://{gate_ip}:5000/start"

        # Send 1000 write requests
        start_time = time.time()
        for i, query in enumerate(write_queries):
            send_request(i, gatekeeper_ip, query)
        end_time = time.time()
        write_time = f"{end_time - start_time:.2f}"

        # Send 1000 read requests
        strategy_time = {}
        for strategy in strategies:
            start_time = time.time()
            for i, query in enumerate(read_queries):
                send_request(i, gatekeeper_ip, query, strategy)
            end_time = time.time()
            strategy_time[strategy] = f"{end_time - start_time:.2f}"
        print()
        print(f"\nTotal time taken for 1000 write operations: {write_time} seconds")
        for strategy in strategies:
            print(f"\nTotal time taken for 1000 {strategy} read operations: {strategy_time[strategy]} seconds")

    except requests.exceptions.RequestException as e:
        print(f"Error during requests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
