import os
import time
import asyncio
from supabase import create_client
from functools import partial

async def async_get_balance(user_id: int):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_balance, user_id)


async def async_add_balance(user_id: int, amount: int):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, add_balance, user_id, amount)


async def async_can_claim_daily(user_id: int):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, can_claim_daily, user_id)

# === SUPABASE CONFIG (z ENV na Renderze) ===
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

def _get_user_row(user_id: int) -> dict:
    ensure_user(user_id)
    res = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
    if not res.data:
        raise RuntimeError(f"Brak użytkownika {user_id} po ensure_user – błąd Supabase?")
    return res.data[0]


# === INIT USER (tworzy konto jeśli nie istnieje) ===
def ensure_user(user_id: int):
    supabase.table("users").upsert({
        "user_id": str(user_id),
        "balance": 0,
        "last_daily": 0
    }, on_conflict="user_id", ignore_duplicates=True).execute()


# === BALANCE ===
def get_balance(user_id: int):
    ensure_user(user_id)

    res = supabase.table("users").select("balance").eq("user_id", str(user_id)).execute()
    return res.data[0]["balance"]


# === ADD MONETY ===
def add_balance(user_id: int, amount: int):
    ensure_user(user_id)
    # Atomowy increment przez RPC lub raw SQL
    supabase.rpc("increment_balance", {
        "p_user_id": str(user_id),
        "p_amount": amount
    }).execute()

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
    supabase.rpc("increment_balance", {
        "p_user_id": str(user_id),
        "p_amount": reward
    }).execute()
    supabase.table("users").update({
        "last_daily": now
    }).eq("user_id", str(user_id)).execute()

# === CRIME SYSTEM ===

def get_crime_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("crime_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["crime_count"] or 0


def add_crime_count(user_id: int):
    current = get_crime_count(user_id)

    supabase.table("users").update({
        "crime_count": current + 1
    }).eq("user_id", str(user_id)).execute()


def reset_crime(user_id: int):
    supabase.table("users").update({
        "crime_count": 0
    }).eq("user_id", str(user_id)).execute()

# === REFLEX SYSTEM ===

def get_reflex_used(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("reflex_used").eq("user_id", str(user_id)).execute()
    return res.data[0]["reflex_used"] or 0


def set_reflex_used(user_id: int, value: int):
    supabase.table("users").update({
        "reflex_used": value
    }).eq("user_id", str(user_id)).execute()

def get_roll_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("roll_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["roll_count"] or 0


def set_roll_count(user_id: int, value: int):
    supabase.table("users").update({
        "roll_count": value
    }).eq("user_id", str(user_id)).execute()

def get_rps_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("rps_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["rps_count"] or 0


def set_rps_count(user_id: int, value: int):
    supabase.table("users").update({
        "rps_count": value
    }).eq("user_id", str(user_id)).execute()

def get_casino_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("casino_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["casino_count"] or 0


def set_casino_count(user_id: int, value: int):
    supabase.table("users").update({
        "casino_count": value
    }).eq("user_id", str(user_id)).execute()
    
def get_coinflip_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("coinflip_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["coinflip_count"] or 0


def set_coinflip_count(user_id: int, value: int):
    supabase.table("users").update({
        "coinflip_count": value
    }).eq("user_id", str(user_id)).execute()

# === ROULETTE COUNT ===
def get_roulette_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("roulette_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["roulette_count"] or 0


def set_roulette_count(user_id: int, value: int):
    supabase.table("users").update({
        "roulette_count": value
    }).eq("user_id", str(user_id)).execute()

def get_cards_count(user_id: int):
    ensure_user(user_id)
    res = supabase.table("users").select("cards_count").eq("user_id", str(user_id)).execute()
    return res.data[0]["cards_count"] or 0


def set_cards_count(user_id: int, value: int):
    supabase.table("users").update({
        "cards_count": value
    }).eq("user_id", str(user_id)).execute()

# === JACKPOT POOL (wiersz "global" w tabeli users) ===
def get_jackpot_pool() -> int:
    res = supabase.table("users").select("jackpot_pool").eq("user_id", "global").execute()
    if not res.data or res.data[0]["jackpot_pool"] is None:
        supabase.table("users").upsert({
            "user_id": "global",
            "balance": 0,
            "jackpot_pool": 10000
        }, on_conflict="user_id").execute()
        return 10000
    return res.data[0]["jackpot_pool"]


def set_jackpot_pool(value: int):
    supabase.table("users").update({
        "jackpot_pool": value
    }).eq("user_id", "global").execute()
    
# db.py - dodaj funkcję
def reset_all_daily_limits():
    supabase.table("users").update({
        "casino_count": 0,
        "rps_count": 0,
        "crime_count": 0,
        "reflex_used": 0,
        "roll_count": 0,
        "coinflip_count": 0,
    }).neq("user_id", "-1").execute()
