import os
from flask import Flask, render_template, request, jsonify, g
from flask_cors import CORS
from datetime import datetime, date

from src.db_manager import DatabaseManager
from src.transactions import Transaction
from src.transaction_type import TransactionType

DB_FILE_PATH = 'finance.db'

app = Flask(__name__)
CORS(app)

# --- Database Connection Management ---

def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context. This is the recommended way to handle
    resources in Flask.
    """
    if 'db_manager' not in g:
        try:
            app.logger.info(f"Connecting to database at: {os.path.abspath(DB_FILE_PATH)}")
            g.db_manager = DatabaseManager(db_path=DB_FILE_PATH)
        except Exception as e:
            app.logger.error(f"CRITICAL: Failed to initialize DatabaseManager: {str(e)}")
            raise RuntimeError("Could not connect to the database.") from e
    return g.db_manager

@app.teardown_appcontext
def close_db(exception=None):
    """
    Closes the database connection at the end of the request.
    This is automatically called by Flask.
    """
    db_manager = g.pop('db_manager', None)
    if db_manager is not None:
        db_manager.close()
        app.logger.info("Database connection closed for this context.")

def format_transaction_rows(rows):
    """Converts a list of transaction tuples from DB into a list of dictionaries."""
    columns = ['date', 'description', 'category', 'amount', 'type', 'id']
    formatted_transactions = []
    if rows:
        for row in rows:
            transaction_dict = dict(zip(columns, row))
            if isinstance(transaction_dict.get('date'), date):
                transaction_dict['date'] = transaction_dict['date'].isoformat()
            formatted_transactions.append(transaction_dict)
    return formatted_transactions

# --- Routes ---

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/users/<username>', methods=['POST'])
def create_user(username):
    """
    Creates a new user table.
    """
    try:
        db = get_db()
        db.create_user_table(username)
        return jsonify({"message": f"User '{username}' created successfully."}), 201
    except ValueError as e:
        # This likely means the user already exists, which is not an error.
        return jsonify({"message": str(e)}), 200
    except Exception as e:
        app.logger.error(f"Unexpected error creating user {username}: {str(e)}")
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/users/<username>/transactions', methods=['GET'])
def get_user_transactions(username):
    """Gets all transactions for a user."""
    try:
        db = get_db()
        transactions_data = db.get_all_transactions(username)
        return jsonify(format_transaction_rows(transactions_data)), 200
    except Exception as e:
        app.logger.error(f"Unexpected error getting all transactions for {username}: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions', methods=['POST'])
def add_user_transaction(username):
    """Adds a new transaction for a user."""
    db = get_db()
    if db.check_username_availability(username):
        app.logger.warning(f"Add transaction attempt for non-existent user: {username}")
        return jsonify({"error": f"User '{username}' does not exist. Create the user first."}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload. Request body is empty or not JSON."}), 400

    required_fields = ['date', 'description', 'category', 'amount', 'type']
    if not all(field in data for field in required_fields):
        missing = [field for field in required_fields if field not in data]
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        new_transaction = Transaction(
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            description=str(data['description']),
            category=str(data['category']),
            amount=float(data['amount']),
            type=TransactionType(data['type'])
        )
        transaction_id = db.add_transaction(username, new_transaction)
        app.logger.info(f"Transaction {transaction_id} added for user: {username}")
        return jsonify({"message": "Transaction added successfully.", "transactionId": transaction_id}), 200
    except ValueError as e:
        app.logger.warning(f"ValueError adding transaction for {username}: {str(e)}. Data: {data}")
        return jsonify({"error": f"Invalid data provided: {str(e)}"}), 400
    except Exception as e:
        app.logger.error(f"Unexpected error adding transaction for {username}: {str(e)}. Data: {data}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions/<int:transaction_id>', methods=['PUT'])
def update_user_transaction(username, transaction_id):
    """Updates an existing transaction for a user."""
    db = get_db()
    if db.check_username_availability(username):
        return jsonify({"error": f"User '{username}' does not exist."}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload."}), 400

    required_fields = ['date', 'description', 'category', 'amount', 'type']
    if not all(field in data for field in required_fields):
        missing = [field for field in required_fields if field not in data]
        return jsonify({"error": f"Missing fields for update: {', '.join(missing)}"}), 400

    try:
        updated_transaction = Transaction(
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            description=str(data['description']),
            category=str(data['category']),
            amount=float(data['amount']),
            type=TransactionType(data['type'])
        )
        db.update_transaction_by_id(username, transaction_id, updated_transaction)
        app.logger.info(f"Transaction {transaction_id} updated for user: {username}")
        return jsonify({"message": f"Transaction ID {transaction_id} updated successfully."}), 200
    except ValueError as e:
        return jsonify({"error": f"Invalid data provided: {str(e)}"}), 400
    except Exception as e:
        app.logger.error(f"Unexpected error updating transaction {transaction_id} for {username}: {str(e)}. Data: {data}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions/<int:transaction_id>', methods=['DELETE'])
def delete_user_transaction(username, transaction_id):
    """Deletes a transaction for a user."""
    db = get_db()
    if db.check_username_availability(username):
        return jsonify({"error": f"User '{username}' does not exist."}), 404
    try:
        db.delete_transaction_by_id(username, transaction_id)
        app.logger.info(f"Transaction {transaction_id} deleted for user: {username}")
        return jsonify({"message": f"Transaction ID {transaction_id} deleted successfully."}), 200
    except Exception as e:
        app.logger.error(f"Unexpected error deleting transaction {transaction_id} for {username}: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions/category/<category_name>', methods=['GET'])
def get_user_transactions_by_category(username, category_name):
    """Gets transactions for a user filtered by category."""
    try:
        db = get_db()
        transactions_data = db.get_category_transactions(username, category_name)
        return jsonify(format_transaction_rows(transactions_data)), 200
    except Exception as e:
        app.logger.error(f"Unexpected error getting category '{category_name}' transactions for {username}: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions/debits', methods=['GET'])
def get_user_debit_transactions(username):
    """Gets all debit transactions (Despesa) for a user."""
    try:
        db = get_db()
        transactions_data = db.get_all_debits(username)
        return jsonify(format_transaction_rows(transactions_data)), 200
    except Exception as e:
        app.logger.error(f"Unexpected error getting debit transactions for {username}: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions/credits', methods=['GET'])
def get_user_credit_transactions(username):
    """Gets all credit transactions (Receita) for a user."""
    try:
        db = get_db()
        transactions_data = db.get_all_credits(username)
        return jsonify(format_transaction_rows(transactions_data)), 200
    except Exception as e:
        app.logger.error(f"Unexpected error getting credit transactions for {username}: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/users/<username>/transactions/month/<int:year>/<int:month>', methods=['GET'])
def get_user_transactions_by_month(username, year, month):
    """Gets transactions for a user filtered by month and year."""
    if not (1 <= month <= 12):
        return jsonify({"error": "Invalid month. Must be between 1 and 12."}), 400
    try:
        db = get_db()
        transactions_data = db.get_month_transactions(username, month, year)
        return jsonify(format_transaction_rows(transactions_data)), 200
    except Exception as e:
        app.logger.error(f"Unexpected error getting month {year}-{month} transactions for {username}: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    app.logger.info("Starting Flask development server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
