import pytest
from app import app
import os
from app import initialize_database, db_manager
from src.db_manager import DatabaseManager

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def clean_db():
    test_db_path = 'finance.db'
    if db_manager is not None and db_manager.connection:
        db_manager.close()  # ← fecha conexão ativa

    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except PermissionError:
            print("Erro: arquivo está em uso. Tentando novamente após aguardar...")
            import time
            time.sleep(0.5)
            os.remove(test_db_path)

    yield

    if db_manager is not None and db_manager.connection:
        db_manager.close()

    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
def prepare_user():

    created_users = set()

    def _prepare(user: str):
        if user not in created_users:
            db = DatabaseManager('finance.db')
            if db.check_username_availability(user):
                db.create_user_table(user)
            db.close()
            initialize_database()
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
    assert not any(tx["id"] == tx_id for tx in data)

def test_filter_by_category(client, prepare_user):
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
