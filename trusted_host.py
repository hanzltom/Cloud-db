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
        r"(--|\b(ALTER|DROP|DELETE|UPDATE|TRUNCATE|EXEC|OR|TRUE)\b)",  # Dangerous SQL keywords
        #r"([';])+|(--)+",  # Detects ' or ; or -- which are common in SQL injection
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            print("Possible SQL injection detected")
            return False, "Possible SQL injection detected"

    if query.strip().lower().startswith("select"):
        # Reject query if WHERE clause is missing or empty
        if re.search(r"(?i)\bSELECT\b.*\bFROM\b.*\bWHERE\b.*[^\s]", query, re.IGNORECASE) is None:
            return False, "Missing where in query"

    if not authorization:
        return False, "Authorization required"

    # Check for query length
    if len(query) > 1000:  # Example max length; adjust as necessary
        print("Query too large")
        return False, "Query too large"

    return True, "Good"

@app.route('/validate', methods=['POST'])
def execute_query():
    data = request.get_json()
    query = data.get("query")
    authorization = data.get("Authorization")
    routing_strategy = data.get("strategy", "round-robin")

    result_validate, str_res = validate(query, authorization)
    if not result_validate:
        return jsonify({"error": f"{str_res}"}), 400

    modified_data = {"query": query, "strategy": routing_strategy}

    try:
        response = requests.post(f"http://{proxy_ip}:5000/query", json=modified_data)
        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)