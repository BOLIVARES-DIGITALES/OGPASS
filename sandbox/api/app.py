from flask import Flask, jsonify, request
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

WALLETS_FILE = BASE_DIR / "data" / "wallets.json"
TRANSACTIONS_FILE = BASE_DIR / "data" / "transactions.json"
CREDENTIALS_FILE = BASE_DIR / "data" / "credentials.json"


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/health")
def health():
    return jsonify({
        "service": "ogpass-sandbox",
        "status": "ok"
    })


@app.get("/wallet/<folio>")
def wallet(folio):
    wallets = load_json(WALLETS_FILE, {})

    wallet_data = wallets.get(folio)

    if not wallet_data:
        return jsonify({
            "error": "wallet_not_found"
        }), 404

    return jsonify({
        "folio": folio,
        **wallet_data
    })


@app.get("/credential/<uid>")
def credential(uid):
    uid = uid.upper()

    credentials = load_json(CREDENTIALS_FILE, {})
    credential_data = credentials.get(uid)

    if not credential_data:
        return jsonify({
            "error": "credential_not_found",
            "uid": uid
        }), 404

    return jsonify({
        "uid": uid,
        **credential_data
    })


@app.post("/authorize")
def authorize():
    payload = request.get_json(silent=True) or {}

    uid = str(payload.get("uid", "")).strip().upper()
    terminal_id = str(
        payload.get("terminal_id", "UNKNOWN")
    ).strip()

    amount = payload.get("amount", 1)

    if not uid:
        return jsonify({
            "status": "DECLINED",
            "reason": "missing_uid"
        }), 400

    if not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({
            "status": "DECLINED",
            "reason": "invalid_amount"
        }), 400

    credentials = load_json(CREDENTIALS_FILE, {})

    credential_data = credentials.get(uid)

    if not credential_data:
        return jsonify({
            "status": "DECLINED",
            "reason": "unknown_credential",
            "uid": uid
        }), 404

    if credential_data.get("status") != "active":
        return jsonify({
            "status": "DECLINED",
            "reason": "credential_inactive",
            "uid": uid
        }), 403

    folio = credential_data.get("folio")

    if not folio:
        return jsonify({
            "status": "DECLINED",
            "reason": "credential_without_wallet"
        }), 500

    wallets = load_json(WALLETS_FILE, {})

    wallet_data = wallets.get(folio)

    if not wallet_data:
        return jsonify({
            "status": "DECLINED",
            "reason": "wallet_not_found"
        }), 404

    if wallet_data.get("status") != "active":
        return jsonify({
            "status": "DECLINED",
            "reason": "wallet_inactive"
        }), 403

    balance_before = wallet_data.get("balance", 0)

    if balance_before < amount:
        return jsonify({
            "status": "DECLINED",
            "reason": "insufficient_balance",
            "folio": folio,
            "balance": balance_before
        }), 402

    balance_after = balance_before - amount

    wallet_data["balance"] = balance_after
    wallets[folio] = wallet_data

    save_json(WALLETS_FILE, wallets)

    transactions = load_json(
        TRANSACTIONS_FILE,
        []
    )

    transaction = {
        "id": str(uuid4()),
        "credential_id": credential_data.get(
            "credential_id"
        ),
        "uid": uid,
        "folio": folio,
        "terminal_id": terminal_id,
        "amount": amount,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "status": "APPROVED",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }

    transactions.append(transaction)

    save_json(
        TRANSACTIONS_FILE,
        transactions
    )

    return jsonify(transaction), 200


@app.get("/transactions")
def transactions():
    data = load_json(
        TRANSACTIONS_FILE,
        []
    )

    return jsonify(data)


@app.get("/transactions/<folio>")
def transactions_by_wallet(folio):
    data = load_json(
        TRANSACTIONS_FILE,
        []
    )

    filtered = [
        tx for tx in data
        if tx.get("folio") == folio
    ]

    return jsonify(filtered)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True
    )