import os
import time
from supabase import create_client

# === SUPABASE CONFIG (z ENV na Renderze) ===
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

# === INIT USER (tworzy konto jeśli nie istnieje) ===
def ensure_user(user_id: int):
    res = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()


    if not res.data:
        supabase.table("users").insert({
            "user_id": str(user_id),
            "balance": 0,
            "last_daily": 0
        }).execute()


# === BALANCE ===
def get_balance(user_id: int):
    ensure_user(user_id)

    res = supabase.table("users").select("balance").eq("user_id", str(user_id)).execute()
    return res.data[0]["balance"]


# === ADD MONETY ===
def add_balance(user_id: int, amount: int):
    ensure_user(user_id)

    current = get_balance(user_id)

    supabase.table("users").update({
        "balance": current + amount
    }).eq("user_id", str(user_id)).execute()

# === SET BALANCE (opcjonalne) ===
def set_balance(user_id: int, amount: int):
    ensure_user(user_id)

    supabase.table("users").update({
        "balance": amount
    }).eq("user_id", str(user_id)).execute()

# === DAILY CHECK ===
def can_claim_daily(user_id: int):
    ensure_user(user_id)

    res = supabase.table("users").select("last_daily").eq("user_id", str(user_id)).execute()
    last = res.data[0]["last_daily"]

    now = int(time.time())
    return now - last >= 86400

# === CLAIM DAILY ===
def claim_daily(user_id: int, reward: int = 10):
    ensure_user(user_id)

    now = int(time.time())

    current = get_balance(user_id)

    supabase.table("users").update({
        "balance": current + reward,
        "last_daily": now
    }).eq("user_id", str(user_id)).execute()
