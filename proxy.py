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
manager_url = f"http://{worker_ip1}:3306"
worker_urls = [f"http://{worker_ip1}:3306", f"http://{worker_ip2}:3306"]


# Round-robin counter to distribute requests to workers
worker_index = 0

@app.route("/query", methods=["POST"])
def proxy_query():
    global worker_index
    data = request.get_json()
    query_type = data.get("type")
    query = data.get("query")

    if not query_type or not query:
        return jsonify({"error": "Missing 'type' or 'query' in request"}), 400

    # Choose target based on query type
    if query_type == "select":
        # Forward to the next worker in round-robin fashion
        target_url = worker_urls[worker_index]
        worker_index = (worker_index + 1) % len(worker_urls)
    else:
        # Non-select queries go to the manager
        target_url = manager_url

    try:
        # Forward the query to the selected target database
        response = requests.post(f"{target_url}/execute", json={"query": query})
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
