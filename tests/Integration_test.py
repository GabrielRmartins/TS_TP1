import pytest
from app import app, get_db
import os

@pytest.fixture
def client():
    """
    A robust fixture that leverages Flask's application context for testing.
    1. Sets the app to TESTING mode.
    2. Creates the database within an application context.
    3. Yields a test client for the test function to use.
    4. After the test, the @app.teardown_appcontext function we added in
       app.py automatically handles closing the database connection.
    5. Finally, the test database file is removed to ensure each test
       is isolated and starts with a clean slate.
    """
    test_db_path = 'finance.db'
    app.config['TESTING'] = True

    with app.app_context():
        get_db()
        
        yield app.test_client()

    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
def prepare_user(client):
    """
    This fixture prepares a user by making an API call to create their table.
    It uses the client provided by the 'client' fixture.
    """
    created_users = set()
    def _prepare(user: str):
        if user not in created_users:
            res = client.post(f"/users/{user}")
            assert res.status_code in [201, 200]
            created_users.add(user)
    return _prepare



def test_create_transaction(client, prepare_user):
    user = "test_user1"
    prepare_user(user)

    payload = {
        "date": "2025-06-25",
        "description": "Freelance",
        "category": "Trabalho",
        "amount": 1200.50,
        "type": "Receita"
    }
    res = client.post(f"/users/{user}/transactions", json=payload)
    assert res.status_code == 200
    json_data = res.get_json()
    assert "transactionId" in json_data

def test_list_transactions(client, prepare_user):
    user = "test_user2"
    prepare_user(user)

    payload = {
        "date": "2025-06-20",
        "description": "Supermercado",
        "category": "Alimentação",
        "amount": 200.00,
        "type": "Despesa"
    }
    post_res = client.post(f"/users/{user}/transactions", json=payload)
    assert post_res.status_code == 200

    res = client.get(f"/users/{user}/transactions")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert any(tx["description"] == "Supermercado" for tx in data)

def test_update_transaction(client, prepare_user):
    user = "test_user3"
    prepare_user(user)

    payload = {
        "date": "2025-06-10",
        "description": "Internet",
        "category": "Serviços",
        "amount": 99.90,
        "type": "Despesa"
    }
    res = client.post(f"/users/{user}/transactions", json=payload)
    assert res.status_code == 200
    json_data = res.get_json()

    tx_id = json_data["transactionId"]

    updated = payload.copy()
    updated["description"] = "Internet Fibra"
    updated["amount"] = 120.00

    res2 = client.put(f"/users/{user}/transactions/{tx_id}", json=updated)
    assert res2.status_code == 200

def test_delete_transaction(client, prepare_user):
    user = "test_user4"
    prepare_user(user)

    payload = {
        "date": "2025-06-01",
        "description": "Academia",
        "category": "Saúde",
        "amount": 80.00,
        "type": "Despesa"
    }
    res = client.post(f"/users/{user}/transactions", json=payload)
    assert res.status_code == 200
    tx_id = res.get_json()["transactionId"]

    res2 = client.delete(f"/users/{user}/transactions/{tx_id}")
    assert res2.status_code == 200

    res3 = client.get(f"/users/{user}/transactions")
    assert res3.status_code == 200
    data = res3.get_json()
    assert not any(tx.get("id") == tx_id for tx in data)

def test_filter_by_category_one_category(client, prepare_user):
    user = "test_user5"
    prepare_user(user)

    payload = {
        "date": "2025-06-05",
        "description": "Pizza",
        "category": "Alimentação",
        "amount": 50.00,
        "type": "Despesa"
    }
    res_post = client.post(f"/users/{user}/transactions", json=payload)
    assert res_post.status_code == 200

    res = client.get(f"/users/{user}/transactions/category/Alimentação")
    assert res.status_code == 200
    data = res.get_json()
    assert all(tx["category"] == "Alimentação" for tx in data)

def test_filter_by_category_multiple_categories(client, prepare_user):
    user = "test_user6"
    prepare_user(user)

    # Add transactions in different categories
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-06-10", "description": "Cinema", "category": "Entretenimento",
        "amount": 30.00, "type": "Despesa"
    })
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-06-15", "description": "Restaurante", "category": "Alimentação",
        "amount": 70.00, "type": "Despesa"
    })
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-06-20", "description": "Livros", "category": "Educação",
        "amount": 45.00, "type": "Despesa"
    })

    res = client.get(f"/users/{user}/transactions/category/Alimentação")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["description"] == "Restaurante"

def test_filter_by_category_no_transactions(client, prepare_user):
    user = "test_user_no_transactions"
    prepare_user(user)

    res = client.get(f"/users/{user}/transactions/category/Alimentação")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 0

def test_get_debit_transactions(client, prepare_user):
    """
    Tests fetching only debit (Despesa) transactions.
    """
    user = "test_user_debit"
    prepare_user(user)

    # Add a credit transaction
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-07-10", "description": "Salary", "category": "Work",
        "amount": 3000.00, "type": "Receita"
    })
    # Add a debit transaction
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-07-15", "description": "Groceries", "category": "Food",
        "amount": 150.00, "type": "Despesa"
    })

    res = client.get(f"/users/{user}/transactions/debits")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["description"] == "Groceries"
    assert data[0]["type"] == "Despesa"

def test_get_credit_transactions(client, prepare_user):
    """
    Tests fetching only credit (Receita) transactions.
    """
    user = "test_user_credit"
    prepare_user(user)

    # Add a credit transaction
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-08-01", "description": "Freelance Payment", "category": "Work",
        "amount": 500.00, "type": "Receita"
    })
    # Add a debit transaction
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-08-05", "description": "Dinner", "category": "Food",
        "amount": 75.00, "type": "Despesa"
    })

    res = client.get(f"/users/{user}/transactions/credits")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["description"] == "Freelance Payment"
    assert data[0]["type"] == "Receita"

def test_filter_by_month(client, prepare_user):
    """
    Tests filtering transactions by a specific month and year.
    """
    user = "test_user_month_filter"
    prepare_user(user)

    # Transactions in June 2025
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-06-10", "description": "Concert Tickets", "category": "Entertainment",
        "amount": 120.00, "type": "Despesa"
    })
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-06-25", "description": "Bonus", "category": "Work",
        "amount": 1000.00, "type": "Receita"
    })
    # Transaction in July 2025
    client.post(f"/users/{user}/transactions", json={
        "date": "2025-07-05", "description": "New Book", "category": "Shopping",
        "amount": 40.00, "type": "Despesa"
    })

    res = client.get(f"/users/{user}/transactions/month/2025/6")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    # Check that both returned transactions are from June
    assert all(tx["date"].startswith("2025-06") for tx in data)