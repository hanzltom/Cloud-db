from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

try:
    with open('trusted_host_ip.txt', 'r') as file:
        trusted_host_ip = file.read().strip()
except FileNotFoundError:
    print("No files found.")

@app.route('/start', methods=['POST'])
def execute_query():
    data = request.get_json()
    query = data.get("query")
    routing_strategy = data.get("strategy", "round-robin")
    modified_data = {"Authorization": True, "query": query, "strategy": routing_strategy}

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        response = requests.post(f"http://{trusted_host_ip}:5000/validate", json=modified_data)
        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)