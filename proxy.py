from flask import Flask, request, jsonify
import requests
import random
import time

app = Flask(__name__)

try:
    with open('workers_ip.txt', 'r') as file:
        worker_ip1, worker_ip2 = file.read().strip().split()

    with open('manager_ip.txt', 'r') as file:
        manager_ip = file.read().strip()
except FileNotFoundError:
    print("No files found.")

manager_url = f"http://{manager_ip}:5000"
worker_urls = [f"http://{worker_ip1}:5000", f"http://{worker_ip2}:5000"]

worker_index = 0

# Function to calculate ping time to each worker
def get_ping_times():
    ping_times = []
    for worker in worker_urls:
        start_time = time.time()
        try:
            # Send a request to measure response time
            response = requests.get(f"{worker}/ping", timeout=2)
            if response.status_code == 200:
                round_trip_time = (time.time() - start_time) * 1000
                ping_times.append((worker, round_trip_time))
            else:
                ping_times.append((worker, float("inf")))
        except requests.exceptions.RequestException:
            # Set to high ping time if unreachable
            ping_times.append((worker, float("inf")))
    return ping_times


@app.route("/query", methods=["POST"])
def proxy_query():
    global worker_index
    data = request.get_json()
    query = data.get("query")
    routing_strategy = data.get("strategy", "round-robin")  # Default to round-robin if not specified

    if not query:
        return jsonify({"error": "Missing 'query' in request"}), 400

    # Determine query type based on the query content
    query_type = "select" if query.strip().lower().startswith("select") else "insert"
    if query.strip().lower().startswith("select"):
        query_type = "select"
    elif query.strip().lower().startswith("insert"):
        query_type = "insert"
    elif query.strip().lower().startswith("delete"):
        query_type = "delete"
    else:
        query_type = "other"

    if query_type == "select" or query_type == "other":
        # Implement routing strategies
        if routing_strategy == "direct":
            # Forward to the manager
            target_url = manager_url
        elif routing_strategy == "random":
            # Randomly choose a worker
            target_url = random.choice(worker_urls)
        elif routing_strategy == "customized":
            # Choose the worker with the lowest ping time
            ping_times = get_ping_times()
            target_url = min(ping_times, key=lambda x: x[1])[0]
        else:
            # Default to round-robin
            routing_strategy = "round-robin"
            target_url = worker_urls[worker_index]
            worker_index = (worker_index + 1) % len(worker_urls)
    else:
        # Non-select queries go to the manager
        target_url = manager_url

    modified_data = {"type": query_type, "query": query}

    try:
        # Forward the query to the selected target database
        response = requests.post(f"{target_url}/execute", json=modified_data)
        response_data = response.json()
        if query_type == "select" or query_type == "other":
            worker_type = f"{routing_strategy} worker IP: {target_url.split("//")[1].split(":")[0]}"
            if routing_strategy == "customized":
                worker_type = f"{worker_type}, ping times: {ping_times}"
        else:
            worker_type = "manager"

        response_data["source"] = worker_type
        return jsonify(response_data), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
