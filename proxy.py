from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

try:
    with open('workers_ip.txt', 'r') as file:
        worker_ip1, worker_ip2 = file.read().strip().split()

    with open('manager_ip.txt', 'r') as file:
        manager_ip = file.read().strip()
except FileNotFoundError:
    print("No files found.")

# Define the IP addresses of the manager and workers
manager_url = f"http://{manager_ip}:5000"  # Port 5000 for your Flask app
worker_urls = [f"http://{worker_ip1}:5000", f"http://{worker_ip2}:5000"]

# Round-robin counter to distribute requests to workers
worker_index = 0

@app.route("/query", methods=["POST"])
def proxy_query():
    global worker_index
    data = request.get_json()
    query = data.get("query")

    if not query:
        return jsonify({"error": "Missing 'query' in request"}), 400

    # Determine query type based on the query content
    query_type = "select" if query.strip().lower().startswith("select") else "insert"
    if query.strip().lower().startswith("select"):
        query_type = "select"
    elif query.strip().lower().startswith("insert"):
        query_type = "insert"
    else:
        return jsonify({"Incorrect action in query"}), 500

    # Choose target based on query type
    if query_type == "select":
        # Forward to the next worker in round-robin fashion
        target_url = worker_urls[worker_index]
        worker_index = (worker_index + 1) % len(worker_urls)
    else:
        # Non-select queries go to the manager
        target_url = manager_url

    # Forward the modified JSON payload with the type added
    modified_data = {"type": query_type, "query": query}

    try:
        # Forward the query to the selected target database
        response = requests.post(f"{target_url}/execute", json=modified_data)
        response_data = response.json()
        worker_type = f"workers[{worker_index - 1}]" if query_type == "select" else "manager"
        response_data["source"] = worker_type  # Add source information to the response
        return jsonify(response_data), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
