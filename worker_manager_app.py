from flask import Flask, request, jsonify
import mysql.connector
import os

app = Flask(__name__)

# Database configuration
DB_HOST = "localhost"
DB_USER = "replica"
DB_PASSWORD = "replica_password"  # Replace with the actual password you set
DB_NAME = "sakila"


@app.route('/execute', methods=['POST'])
def execute_query():
    data = request.get_json()
    query = data.get("query")

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Connect to MySQL database
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Execute the query
        cursor.execute(query)

        # Commit only for non-select queries
        if query.strip().lower().startswith("select"):
            result = cursor.fetchall()
            columns = cursor.column_names
            response = {"result": [dict(zip(columns, row)) for row in result]}
        else:
            conn.commit()
            response = {"message": "Query executed successfully"}

        with open('response.txt', 'w') as file:
            file.write(f"{response}")
        cursor.close()
        conn.close()

        return jsonify(response), 200

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
