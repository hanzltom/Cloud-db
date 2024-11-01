from flask import Flask, request, jsonify
import requests
import re
import os

app = Flask(__name__)

try:
    with open('proxy_ip.txt', 'r') as file:
        proxy_ip = file.read().strip()
except FileNotFoundError:
    print("No files found.")


def validate(query, authorization):
    # Basic SQL injection prevention patterns
    forbidden_patterns = [
        r"(--|\b(ALTER|DROP|DELETE|INSERT|UPDATE|TRUNCATE|EXEC)\b)",  # Dangerous SQL keywords
        r"([';])+|(--)+",  # Detects ' or ; or -- which are common in SQL injection
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            print("Possible SQL injection detected")
            return False

    if not authorization:
        return False

    # Check for query length
    if len(query) > 1000:  # Example max length; adjust as necessary
        print("Query too large")
        return False

    return True

@app.route('/validate', methods=['POST'])
def execute_query():
    data = request.get_json()
    query = data.get("query")
    authorization = data.get("authorization")


    if not validate(query, authorization):
        return jsonify({"error": "No authorization, forbidding request"}), 400

    modified_data = {"query": query,}


    try:
        response = requests.post(f"{proxy_ip}:5000/query", json=modified_data)
        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)