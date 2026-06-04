import os
import discord
import random
import io
import asyncio
import aiohttp
import time
import datetime
import logging
import traceback
import sys
import faulthandler
import math
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from collections import Counter
from db import (
    get_balance,
    add_balance,
    set_balance,
    can_claim_daily,
    claim_daily,
    async_can_claim_daily,
    get_crime_count,
    add_crime_count,
    get_casino_count,
    set_casino_count,
    get_roll_count,
    set_roll_count,
    get_rps_count,
    set_rps_count,
    get_coinflip_count,
    set_coinflip_count,
    get_reflex_used,
    set_reflex_used,
    reset_all_daily_limits,
    set_jackpot_pool,
    get_jackpot_pool,
    set_cards_count,
    get_cards_count,
    set_roulette_count,
    get_roulette_count,
    supabase
)

faulthandler.enable()


# ---------------- LOGGING ----------------


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ],
    force=True
)


logger = logging.getLogger("discord_bot")


# Discord.py logs
discord.utils.setup_logging(level=logging.INFO)


# asyncio debug
asyncio.get_event_loop().set_debug(True)


# Globalne wyjątki asyncio
def handle_async_exception(loop, context):
    logger.error("ASYNCIO EXCEPTION:")
    logger.error(context)


    exc = context.get("exception")
    if exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__)


loop = asyncio.get_event_loop()
loop.set_exception_handler(handle_async_exception)


# Globalne wyjątki Pythona
def global_exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return


    logger.critical("GLOBAL EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = global_exception_hook
# Python
session = None  # DODAJ przed jakąkolwiek funkcją


DEFAULT_EMBED_COLOUR = 0x2ECC71
ORIGINAL_CTX_SEND = commands.Context.send

async def ctx_send_override(self, content=None, **kwargs):
    if content is not None and isinstance(content, str) and 'embed' not in kwargs:
        embed = discord.Embed(description=content, colour=DEFAULT_EMBED_COLOUR)
        return await ORIGINAL_CTX_SEND(self, embed=embed, **kwargs)
    return await ORIGINAL_CTX_SEND(self, content=content, **kwargs)

commands.Context.send = ctx_send_override

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15)

# --- konfiguracja z ENV ---
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")
MODERATORS = [int(x) for x in os.environ.get("MODERATORS", "").split(",") if x.strip()]


ALLOWED_GUILD_ID = 1352031903322210456

if not TOKEN:
    raise RuntimeError("Brak DISCORD_TOKEN w zmiennych środowiskowych")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='?', intents=intents, help_command=None)

@bot.check
def globally_block_other_servers(ctx):
    return ctx.guild and ctx.guild.id == ALLOWED_GUILD_ID



# ---- Flask ping ----
app = Flask("")

@app.route("/")
def home():
    logger.info("FLASK PING RECEIVED")
    return "Bot alive"


def run_flask():
    try:
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        print(f"Flask error: {e}")

Thread(target=run_flask, daemon=True).start()

@bot.event
async def on_ready():
    global session


    logger.info(f'BOT READY: {bot.user} ({bot.user.id})')


    try:
        if session is None or session.closed:
            logger.info("Creating aiohttp session")
            session = aiohttp.ClientSession(timeout=HTTP_TIMEOUT)


        if not christmas_loop.is_running():
            logger.info("Starting christmas_loop")
            christmas_loop.start()


        if not daily_reset_loop.is_running():
            logger.info("Starting daily_reset_loop")
            daily_reset_loop.start()

        if not watchdog_loop.is_running():
            logger.info("Starting watchdog_loop")
            watchdog_loop.start()

        if not hasattr(bot, '_ladder_started'):
            logger.info("Starting ladder_system_task")
            bot._ladder_started = True
            asyncio.create_task(ladder_system_task())


    except Exception:
        logger.exception("ERROR INSIDE on_ready")

@bot.event
async def on_disconnect():
    logger.warning("DISCORD DISCONNECTED")


@bot.event
async def on_resumed():
    logger.info("DISCORD SESSION RESUMED")


@bot.event
async def on_connect():
    logger.info("DISCORD CONNECTED")


@bot.event
async def on_error(event, *args, **kwargs):
    logger.exception(f"DISCORD EVENT ERROR: {event}")

@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_GUILD_ID:
        print(f"Leaving guild: {guild.name} ({guild.id})")
        await guild.leave()

@tasks.loop(time=datetime.time(hour=0, minute=0))  # dokładnie północ UTC
async def daily_reset_loop():
    print("[CRON] Reset dziennych limitów...")
    await asyncio.get_event_loop().run_in_executor(None, reset_all_daily_limits)

@tasks.loop(minutes=1)
async def watchdog_loop():
    try:
        latency = bot.latency


        logger.info(
            f"WATCHDOG | latency={latency:.3f}s | "
            f"closed={bot.is_closed()} | "
            f"ready={bot.is_ready()}"
        )


        # Jeśli websocket zdechł
        if bot.is_closed():
            logger.critical("BOT CLOSED - EXITING PROCESS")
            os._exit(1)


        # absurdalny ping = loop problem
        if latency > 10:
            logger.critical(f"EXTREME LATENCY DETECTED: {latency}")
            
    except Exception:
        logger.exception("WATCHDOG ERROR")

def get_ladder(balance: int):
    for name, min_v, max_v, _desc in LADDERS:
        if min_v <= balance <= max_v:
            return name, f"{min_v}-{max_v}"
    return LADDERS[0][0], "0-5000"

async def ladder_system_task():
    while True:
        now = time.localtime()
        if now.tm_hour == 0 and now.tm_min == 5:
            print("[LADDER] Aktualizacja lig...")
            users = supabase.table("users").select("*").execute().data


            guild = bot.guilds[0] if bot.guilds else None
            if not guild:
                await asyncio.sleep(60)
                continue


            for user in users:
                user_id = int(user["user_id"])
                balance = user["balance"]
                new_ladder, _ = get_ladder(balance)
                old_ladder = user.get("ladder")


                supabase.table("users").update({"ladder": new_ladder}).eq("user_id", str(user_id)).execute()


                member = guild.get_member(user_id)
                if not member:
                    continue


                role = discord.utils.get(guild.roles, name=new_ladder)
                if role and role not in member.roles:
                    for r, _, _, _ in LADDERS:
                        old_role = discord.utils.get(guild.roles, name=r)
                        if old_role and old_role in member.roles:
                            await member.remove_roles(old_role)
                    await member.add_roles(role)


                    ladder_names = [x[0] for x in LADDERS]
                    if old_ladder is None:
                        msg = f"🪙 Gracz {member.name} dołączył do ligi {new_ladder}!"
                    else:
                        old_index = ladder_names.index(old_ladder) if old_ladder in ladder_names else 0
                        new_index = ladder_names.index(new_ladder)
                        if new_index < old_index:
                            msg = f"📉 Niestety! Gracz {member.name} spadł do {new_ladder}!"
                        else:
                            msg = f"📈 Gratulacje! Gracz {member.name} awansował do {new_ladder}!"


                    channel = discord.utils.get(guild.text_channels, name="general")
                    if channel:
                        await channel.send(msg)


            await asyncio.sleep(60)
        await asyncio.sleep(30)




def start_ladder_system():
    bot.loop.create_task(ladder_system_task())


LADDERS = [
    ("Nowicjusze Systemu", 0, 5000,
     "Czyli oficjalnie: dopiero uczysz się klikać. Nieoficjalnie: serwer jeszcze nie wie, czy masz ambicje czy tylko Wi-Fi."),

    ("Rekruci Obiecanek", 5001, 15000,
     "Zaczynasz udawać, że to dopiero początek. System już cię rozpoznaje, ale nadal nie szanuje."),

    ("Zbieracze Okruszków", 15001, 30000,
     "Pierwszy moment, kiedy ktoś mówi 'o, ma coś tam'. Nadal karmisz się resztkami systemu."),

    ("Lokalni Gracze", 30001, 60000,
     "Masz już pewną pozycję. Czy to imponujące? Nie. Czy przestajesz scrollować? Też nie."),

    ("Operujący Kapitałem", 60001, 100000,
     "Brzmi jak ktoś, kto wie co robi. W praktyce: nie wydajesz wszystkiego na głupoty (jeszcze)."),

    ("Architekci Ekonomii", 100001, 150000,
     "Iluzja władzy. Ludzie patrzą jakbyś miał plan. Ty też udajesz."),

    ("Elita Systemu", 150001, 200000,
     "System działa bardziej dla ciebie niż przeciwko tobie. I to jest niebezpieczne."),

    ("Legendary Bilansu", 200001, 10**18,
     "Nie grasz już w grę. Ty jesteś bugiem ekonomii, który ktoś zostawił, bo nie miał siły go naprawić.")
]

CHRISTMAS_THEMES = {
    "spring_awakening": {
        "name": "Wiosenne przebudzenie / natura",
        "items": [
            {"text": "🌱 Pierwsze liście wyłażą, serwer też powoli budzi się do życia", "query": "spring+leaves+sunlight+morning", "color": 0x58D68D},
            {"text": "🌸 Kwiaty w tle, memy w rękach", "query": "spring+flowers+bloom", "color": 0xEBDEF0},
            {"text": "☀️ Słońce świeci, a ja dalej pod kocem", "query": "spring+sun+cozy+window", "color": 0xF4D03F},
            {"text": "🐦 Ptaki ćwierkają, a odpowiedzi wciąż rzadkie", "query": "birds+spring+morning", "color": 0x5DADE2},
            {"text": "🌿 Wiosenny wiatr = naturalny filtr spamu", "query": "spring+wind+trees", "color": 0x48C9B0},
            {"text": "🌼 Pąki rosną, chaos w czacie też", "query": "flower+buds+spring", "color": 0xF7DC6F},
            {"text": "🏡 Widok z okna: zielono, a produktywność wciąż zimowa", "query": "green+landscape+spring+window", "color": 0x52BE80},
            {"text": "🦋 Motyl przelatuje, użytkownicy też czasem", "query": "butterfly+spring+garden", "color": 0xD7BDE2},
            {"text": "🌳 Drzewo stoi, ja patrzę na powiadomienia", "query": "tree+spring+sunlight", "color": 0x239B56},
            {"text": "🌞 Słońce i lekki chill – obowiązkowo", "query": "spring+sun+relax", "color": 0xF5CBA7},
        ],
    },

    "spring_cleaning": {
        "name": "Porządki / organizacja",
        "items": [
            {"text": "🧹 Wiosenne sprzątanie: serwer nie umyje się sam", "query": "spring+cleaning+home", "color": 0xAAB7B8},
            {"text": "🗂️ Foldery w porządku, a pingów nadal brak", "query": "organized+folders+desk", "color": 0x5D6D7E},
            {"text": "📦 Porządek w chaosie = codzienna sztuka", "query": "minimalist+workspace+clean", "color": 0x85929E},
            {"text": "🧴 Dezynfekcja kanałów w toku", "query": "cleaning+supplies+spring", "color": 0xAED6F1},
            {"text": "📝 Plan dnia: posprzątać i zapomnieć o odpowiedziach", "query": "to+do+list+spring", "color": 0x7FB3D5},
            {"text": "📅 Kalendarz mówi: „nie śpiesz się”", "query": "calendar+spring+planning", "color": 0x5499C7},
            {"text": "🪴 Doniczki poukładane, memy też", "query": "potted+plants+home", "color": 0x27AE60},
            {"text": "🔄 Rotacja dopisków w trybie czystości", "query": "refresh+cycle+clean", "color": 0x48C9B0},
            {"text": "🛋️ Kanapa wciąż królem porządku", "query": "clean+living+room+spring", "color": 0x82E0AA},
            {"text": "🗃️ Sortowanie pingów = minimalna motywacja", "query": "organizing+desk+workspace", "color": 0x566573},
        ],
    },

    "spring_weather": {
        "name": "Pogoda / słońce",
        "items": [
            {"text": "☀️ Słońce świeci, a ja wciąż ignoruję powiadomienia", "query": "bright+sunny+spring+day", "color": 0xF4D03F},
            {"text": "🌤️ Chmury przesłaniają obowiązki", "query": "spring+clouds+sky", "color": 0xD6EAF8},
            {"text": "🌦️ Deszcz? Idealny do pozostania na kanapie", "query": "spring+rain+window", "color": 0x5DADE2},
            {"text": "🌈 Po deszczu memy wychodzą pięknie", "query": "rainbow+after+rain+spring", "color": 0xBB8FCE},
            {"text": "🌬️ Wiatr wieje, a serwer stoi", "query": "windy+spring+trees", "color": 0x7FB3D5},
            {"text": "🌞 Lekkie ocieplenie = powód do herbaty w ogrodzie", "query": "spring+garden+tea", "color": 0xF8C471},
            {"text": "⛅ Chmurka = wymówka do minimalnej aktywności", "query": "partly+cloudy+spring", "color": 0xAED6F1},
            {"text": "🌄 Poranny widok = więcej motywacji, mniej odpowiedzi", "query": "spring+sunrise+landscape", "color": 0xF5B041},
            {"text": "🌱 Świeża zieleń = darmowa dekoracja czatu", "query": "fresh+green+spring+nature", "color": 0x58D68D},
            {"text": "🌸 Kwiaty rosną, a ja czekam na reakcje", "query": "blooming+flowers+spring", "color": 0xF1948A},
        ],
    },

    "spring_memes": {
        "name": "Humor i memy wiosenne",
        "items": [
            {"text": "🐦 Ping jak ptak – czasem przylatuje", "query": "bird+spring+funny", "color": 0x5DADE2},
            {"text": "🌼 Kwiat w roli moderatora dnia", "query": "flower+funny+spring", "color": 0xF7DC6F},
            {"text": "🌞 Słońce świeci, a chaos żyje", "query": "sunny+spring+chaos", "color": 0xF4D03F},
            {"text": "🦋 Motyl taguje przypadkowych użytkowników", "query": "butterfly+funny+spring", "color": 0xD7BDE2},
            {"text": "🐝 Bzyczenie = naturalny alert", "query": "bee+spring+macro", "color": 0xF1C40F},
            {"text": "🌿 Liście spadają? Nie, memy wciąż na miejscu", "query": "spring+leaves+funny", "color": 0x52BE80},
            {"text": "🐞 Biedronka przynosi dobre vibes", "query": "ladybug+spring+macro", "color": 0xE74C3C},
            {"text": "☁️ Chmura przysłania powiadomienia", "query": "cloudy+spring+sky", "color": 0xD6EAF8},
            {"text": "🌳 Drzewo patrzy na kanały, ja na kawę", "query": "tree+spring+coffee", "color": 0x239B56},
            {"text": "🌸 Pąk kwiatowy = codzienny dopisek", "query": "flower+bud+spring+macro", "color": 0xF1948A},
        ],
    },

    "spring_chill": {
        "name": "Chill / odpoczynek",
        "items": [
            {"text": "🛋️ Kanapa w trybie „wiosenny relaks”", "query": "cozy+sofa+spring", "color": 0x82E0AA},
            {"text": "☕ Herbata na świeżym powietrzu", "query": "tea+garden+spring", "color": 0xA569BD},
            {"text": "🎶 Śpiew ptaków zamiast powiadomień", "query": "birds+singing+spring", "color": 0x48C9B0},
            {"text": "🧸 Pluszak nadzoruje spokój czatu", "query": "teddy+bear+spring", "color": 0xAF7AC5},
            {"text": "📖 Książka i chill = wiosenny zestaw dnia", "query": "reading+book+garden", "color": 0x5B2C6F},
            {"text": "🌅 Zachód słońca = minimalne aktywności", "query": "spring+sunset+landscape", "color": 0xF5B041},
            {"text": "🌞 Poranna kawa + serwer w tle", "query": "coffee+morning+spring", "color": 0xDC7633},
            {"text": "🐾 Zwierzak obok, powiadomienia ignorowane", "query": "pet+spring+relax", "color": 0x52BE80},
            {"text": "🪑 Fotel wygodniejszy niż każda komenda", "query": "armchair+spring+cozy", "color": 0x7DCEA0},
            {"text": "🔔 Dzwonek w tle = nie moje powiadomienia", "query": "doorbell+home+spring", "color": 0xA93226},
        ],
    },

    "spring_productivity": {
        "name": "Planowanie i produktywność",
        "items": [
            {"text": "📝 Lista rzeczy do zrobienia: 10% wykonane, 90% ignorowane", "query": "to+do+list+desk+spring", "color": 0x5D6D7E},
            {"text": "📅 Kalendarz mówi: „wiosna = powolne tempo”", "query": "calendar+spring+planning", "color": 0x5499C7},
            {"text": "🔄 Rotacja dopisków w trybie produktywności", "query": "refresh+cycle+workspace", "color": 0x48C9B0},
            {"text": "🏞️ Spacer = powód do przerwy", "query": "spring+walk+park", "color": 0x58D68D},
            {"text": "💡 Pomysł dnia: minimalne działania, maksymalny chill", "query": "minimalism+spring+idea", "color": 0xF7DC6F},
            {"text": "🏡 Widok z okna inspiruje, odpowiedzi nie", "query": "spring+window+view", "color": 0x52BE80},
            {"text": "🌱 Zasadziłem wirtualny kwiat = progres!", "query": "planting+flower+spring", "color": 0x27AE60},
            {"text": "⏳ Czas leci, a ja wciąż na kanapie", "query": "clock+time+relax", "color": 0x95A5A6},
            {"text": "🧭 Kompas pokazuje kierunek do kawy", "query": "compass+direction+coffee", "color": 0x1ABC9C},
            {"text": "🎯 Cel dnia: przeżyć wiosnę bez dram", "query": "spring+goal+focus", "color": 0x2874A6},
        ],
    },
}

# CHRISTMAS_THEMES = {
 #   "winter_traditions": {
  #      "name": "Święta / zimowe tradycje",
   #     "items": [
    #        {"text": "🎄 Choinka włączona, powiadomienia wyciszone", "query": "christmas+tree+lights+cozy", "color": 0x2ECC71},
            #{"text": "🎅 Mikołaj się zgubił, ale pingi nadal docierają", "query": "santa+claus+lost+winter", "color": 0xE74C3C},
           # {"text": "❄️ Śnieg pada, serwer działa… jakoś", "query": "winter+snow+server+night", "color": 0x5DADE2},
          #  {"text": "🕯️ Świeczki zapalone, chaos kontrolowany", "query": "candle+light+cozy+dark", "color": 0xF5B041},
         #   {"text": "🍪 Pierniki są, produktywność nie", "query": "gingerbread+cookies+christmas", "color": 0xD35400},
        #    {"text": "🧦 Skarpety na nogach, memy w rękach", "query": "christmas+socks+cozy", "color": 0xAF7AC5},
       #     {"text": "🎁 Prezenty zapakowane, odpowiedzi brak", "query": "christmas+gifts+wrapped+boxes", "color": 0xF4D03F},
      #      {"text": "🦌 Renifery w trybie patrolu, użytkownicy w trybie snu", "query": "reindeer+winter+night", "color": 0xA04000},
     #       {"text": "⛄ Bałwan stoi, a ja czekam na reakcje", "query": "snowman+winter+snow", "color": 0xAED6F1},
    #        {"text": "🧣 Szalik na szyi, serwer w trybie chill", "query": "scarf+winter+cozy", "color": 0x1ABC9C},
   #     ],
  #  },

 #   "winter_weather": {
   #     "name": "Mróz i zimowa aura",
   #     "items": [
            #{"text": "❄️ Mróz na zewnątrz, Discord w środku działa", "query": "winter+frost+window", "color": 0x85C1E9},
           # {"text": "🌨️ Śnieżyca = idealna wymówka do braku aktywności", "query": "snowstorm+winter", "color": 0x5DADE2},
          #  {"text": "🧊 Lodowata cisza w kanałach", "query": "ice+cold+winter+silence", "color": 0xAAB7B8},
         #   {"text": "🌬️ Wiatr hula, ja siedzę pod kocem", "query": "winter+wind+cozy+blanket", "color": 0x7FB3D5},
        #    {"text": "☃️ Bałwan patrzy, jak nikt nie odpowiada", "query": "snowman+lonely+winter", "color": 0xD6EAF8},
       #     {"text": "🥶 Dłonie zamarznięte, ping nie dotarł", "query": "cold+hands+winter", "color": 0x5D6D7E},
      #      {"text": "❄️ Śnieg = naturalny filtr powiadomień", "query": "falling+snow+winter", "color": 0xEBF5FB},
     #       {"text": "🌫️ Mgła na zewnątrz, chaos w czacie minimalny", "query": "winter+fog+street", "color": 0x99A3A4},
    #        {"text": "🧤 Rękawice na dłoniach, CTRL+C na aktywności", "query": "winter+gloves+cold", "color": 0x566573},
   #         {"text": "🌁 Widoczność spada, tak samo jak moja motywacja", "query": "foggy+winter+city", "color": 0x616A6B},
  #      ],
 #   },
#
  #  "cozy_chill": {
    #    "name": "Herbata, koc i chill",
   #     "items": [
  #          {"text": "☕ Herbata w kubku, nic nie muszę", "query": "tea+cup+cozy", "color": 0xA569BD},
           # {"text": "🛋️ Kanapa w trybie królewskim, serwer w trybie obserwacji", "query": "sofa+cozy+living+room", "color": 0x7DCEA0},
          #  {"text": "🕯️ Światło świec = jedyna energia dnia", "query": "candlelight+dark+cozy", "color": 0xF5CBA7},
         #   {"text": "🧣 Koc + szalik = tryb maksymalnego komfortu", "query": "blanket+scarf+cozy", "color": 0x48C9B0},
        #    {"text": "🍫 Gorąca czekolada rekomendowana przy pingach", "query": "hot+chocolate+cozy", "color": 0x935116},
       #     {"text": "📖 Książka w ręku, czat w spokoju", "query": "reading+book+cozy", "color": 0x5B2C6F},
      #      {"text": "🎶 Świąteczne melodie w tle, odpowiedzi rzadko", "query": "christmas+music+cozy", "color": 0x1F618D},
     #       {"text": "🐾 Zwierzak obok, serwer nadal żyje", "query": "pet+cat+dog+cozy", "color": 0x52BE80},
    #        {"text": "🌙 Noc = czas kreatywnego ignorowania", "query": "night+moon+quiet", "color": 0x2C3E50},
   #         {"text": "🔥 Kominek działa, motywacja offline", "query": "fireplace+cozy+night", "color": 0xCB4335},
  #      ],
 #   },
#
   # "winter_memes": {
  #      "name": "Humor i memy zimowe",
 #       "items": [
#            {"text": "🦌 Rudolf nadal nie odpowiada", "query": "reindeer+winter+funny", "color": 0x873600},
           # {"text": "🎄 Choinka mówi: „Nie dzwońcie, odpoczywam”", "query": "christmas+tree+funny", "color": 0x27AE60},
          #  {"text": "⛄ Bałwan patrzy dziwnie, jak pingi spadają", "query": "snowman+funny+winter", "color": 0xAED6F1},
         #   {"text": "❄️ Mróz = darmowy filtr spamu", "query": "cold+winter+humor", "color": 0x85C1E9},
        #    {"text": "🧦 Skarpety w roli moderatora", "query": "funny+socks+winter", "color": 0xAF7AC5},
       #     {"text": "🎅 Święty Mikołaj ignoruje tagi", "query": "santa+claus+funny", "color": 0xC0392B},
      #      {"text": "☕ Kawa nie rozwiąże wszystkiego, ale pomaga", "query": "coffee+cup+funny", "color": 0x6E2C00},
     #       {"text": "🧣 Szalik zakrywa oczy przed dramatem", "query": "scarf+winter+funny", "color": 0x16A085},
    #        {"text": "🐧 Ping nie dotarł? Ping z pingwinem!", "query": "penguin+winter+funny", "color": 0x2980B9},
   #         {"text": "🛷 Sanie wjechały, chaos też", "query": "sled+winter+chaos", "color": 0xD68910},
  #      ],
 #   },
#
   # "home_vibes": {
  #      "name": "Domowy klimat",
 #       "items": [
#            {"text": "🏠 Kanapa, koc, serwer w tle", "query": "home+cozy+sofa", "color": 0x935116},
           # {"text": "🕯️ Świeczki i spokój", "query": "candles+calm+cozy", "color": 0xF8C471},
          #  {"text": "🧸 Pluszak jako moderator dnia", "query": "teddy+bear+cozy", "color": 0xAF601A},
         #   {"text": "📺 Telewizor włączony, odpowiedzi minimalne", "query": "tv+living+room+cozy", "color": 0x566573},
        #    {"text": "🛋️ Fotel wygodniejszy niż każda komenda", "query": "armchair+cozy+home", "color": 0x7DCEA0},
       #     {"text": "🍪 Przerwa na ciasteczko = wymówka", "query": "cookies+home+cozy", "color": 0xD35400},
      #      {"text": "🐶 Pies blokuje kanał, ja pod kocem", "query": "dog+blanket+cozy", "color": 0x52BE80},
     #       {"text": "🏡 Widok z okna = śnieg i cisza", "query": "winter+window+snow", "color": 0x85C1E9},
    #        {"text": "🎶 Muzyka nastrojowa = serwer chill", "query": "music+cozy+home", "color": 0x76448A},
   #         {"text": "🔔 Dzwonek w tle = nie moje powiadomienia", "query": "doorbell+home", "color": 0xA93226},
  #      ],
 #   },
#
#    "winter_survival": {
  #      "name": "Planowanie i przetrwanie zimy",
 #       "items": [
#            {"text": "📝 Listy rzeczy do zrobienia ignorowane", "query": "to+do+list+desk", "color": 0x5D6D7E},
           # {"text": "📅 Kalendarz mówi „odpocznij”", "query": "calendar+relax", "color": 0x1F618D},
          #  {"text": "🕰️ Czas leci, a ja nadal pod kocem", "query": "clock+time+waiting", "color": 0x7B7D7D},
         #   {"text": "🔥 Ogień w kominku = plan na dzisiaj: nic", "query": "fireplace+relax", "color": 0xCB4335},
        #    {"text": "🎯 Cel dnia: nie zamarznąć", "query": "winter+goal+survival", "color": 0x2874A6},
       #     {"text": "🧭 Kompas pokazuje kierunek do herbaty", "query": "compass+direction", "color": 0x1ABC9C},
      #      {"text": "🏔️ Zimowa wyprawa: do kuchni po czekoladę", "query": "winter+mountains+funny", "color": 0x5DADE2},
    #        {"text": "⏳ Odpowiedzi przyjdą… może", "query": "hourglass+time+waiting", "color": 0x95A5A6},
   #         {"text": "🥶 Przetrwać mróz = sztuka dnia", "query": "cold+winter+survival", "color": 0x5499C7},
  #          {"text": "💡 Pomysł: minimalne działania, maksymalny chill", "query": "minimalism+relax+cozy", "color": 0xF7DC6F},
 #       ],
 #   },
#}

# ---- Tematy świąteczne ----
# CHRISTMAS_THEMES = {
   # "🎄 Choinka": {
      #  "query": "christmas+tree+ornaments+lights",
      #  "color": 0x2ECC71,
 #       "texts": [
#            "🎄 Świąteczna propaganda obowiązkowa",
  #          "🎄 Choinka stoi. Regulamin też.",
   #         "🎄 Ten moment, gdy drzewko ma więcej ozdób niż rola",
    #        "🎄 Administracja potwierdza: to jest choinka",
     #       "🎄 Lampki zapalone = tryb chill on",
      #      "🎄 Gałązka sztuki, odgłos lampek i dramaty w tle"
       # ]
  #  },
   # "🎅 Mikołaj": {
    #    "query": "santa+claus+red+suit+beard+presents+workshop+helper",
     #   "color": 0xE74C3C,
      #  "texts": [
       #     "🎅 Ho ho ho. Logi były sprawdzane.",
        #    "🎅 Mikołaj widzi więcej niż moderator",
         #   "🎅 Prezentów brak, ale klimat jest",
          #  "🎅 Regulamin grzecznych obowiązuje cały rok",
           # "🎅 Pamiętaj: lista grzecznych jest dłuższa niż myślisz",
            #"🎅 Jeśli zostawiłeś ciasteczka, masz przewagę"
     #   ]
    #},
   # "🦌 Renifery": {
  #      "query": "reindeer+rudolph+sleigh+antlers+winter-animals",
 #       "color": 0xA04000,
#        "texts": [
          #  "🦌 Renifer na służbie. Zaprzęg w gotowości.",
         #   "🦌 Rudolf twierdzi, że to nie jego wina",
        #    "🦌 Bez reniferów nie ma logistyki świąt",
       #     "🦌 Ten gość ciągnie cały projekt",
      #      "🦌 Szczęśliwy renifer = termin dostarczony na czas",
     #       "🦌 Zaprzęg gotowy, kawa w kubku, jedziemy"
    #    ]
   # },
  #  "❄️ Zima": {
     #   "query": "winter+snow+snowy+ice+frost",
    #    "color": 0x5DADE2,
   #     "texts": [
          #  "❄️ Zima przyszła. Produktywność wyszła.",
         #   "❄️ Śnieg pada, serwer nadal żyje",
        #    "❄️ Idealna pogoda na nieodpisywanie",
       #     "❄️ Mróz na zewnątrz, ciepło na czacie",
      #      "❄️ Mróz + herbata = plan działania: zero",
     #       "❄️ Śnieżne widowisko, minimalne zaangażowanie"
    #    ]
   # },
    #"🎁 Prezenty": {
   #     "query": "christmas+gifts+presents+wrapping+boxes",
  #      "color": 0xF4D03F,
 #       "texts": [
       #     "🎁 Najlepszy prezent to brak pingów",
      #      "🎁 Administracja nic nie obiecuje",
     #       "🎁 Opakowanie ładniejsze niż zawartość",
    #        "🎁 Tak, to też się liczy",
   #         "🎁 Prezenty pakowane specjalnie: poziom chaosu",
  #          "🎁 Jeśli dostałeś skarpetki — interpretuj to jako inwestycję"
 #       ]
#    },
  #  "☕ Klimat": {
 #       "query": "christmas+cozy+hot-chocolate+blanket+fireplace",
#        "color": 0xAF7AC5,
        #"texts": [
       #     "☕ Tryb koc + herbata aktywny",
      #      "☕ Oficjalnie: nic nie musisz",
     #       "☕ To nie lenistwo, to święta",
    #        "☕ Discord, cisza i zero planów",
   #         "☕ Kocyk ⊕ herbata = 100% efektywności relaksu",
  #          "☕ Kiedy świat płonie, parzę herbatę"
    #    ]
   # },
  #  "🏠 Dom": {
  #      "query": "christmas+home+cozy-home+family+decor",
 #      "color": 0xDC7633,
#        "texts": [
          #  "🏠 Domowy tryb serwera",
         #   "🏠 Bez pośpiechu, bez dram",
        #    "🏠 Nawet bot zwalnia tempo",
       #     "🏠 Tu się odpoczywa",
      #      "🏠 Kanapa królem, pilot władcą świata",
     #       "🏠 Zapach piernika rekomendowany"
    #    ]
   # },
  #  "🔥 Ogień": {
 #       "query": "fireplace+winter+cozy-fire+embers+hearth",
#        "color": 0xCB4335,
       # "texts": [
         #   "🔥 Idealne tło do ignorowania obowiązków",
       #     "🔥 Ogień trzaska, czat żyje",
      #      "🔥 Legalne źródło ciepła",
     #       "🔥 Klimat zatwierdzony",
    #        "🔥 Siedzimy przy ogniu, planów brak",
    #        "🔥 Ogień = dobry pretekst do dramy (ale miłej)"
   #     ]
   # },
    #"🌌 Noc": {
        #"query": "christmas+night+stars+night-sky+twilight",
        #"color": 0x1F618D,
        #"texts": [
        #    "🌌 Nocna wersja świąt",
       #     "🌌 Cisza, spokój, Discord",
      #      "🌌 Idealna pora na memy",
     #       "🌌 Bot nadal czuwa. Niestety.",
    #        "🌌 Nocą wszystko wygląda lepiej z lampkami",
   #         "🌌 Gwiazdy, cisza i podejrzane myśli o prezentach"
  #      ]
 #   }
#}


#CHRISTMAS_THEMES = {
  #  "summer_weather": {
 #       "name": "Słońce i pogoda",
#        "items": [
            #{"text": "🌞 Słońce praży, serwer działa w trybie slow-motion", "query": "summer+sun+heat+bright", "color": 0xF4D03F},
           # {"text": "🌤️ Chmurka raz na kilka dni – jako niespodzianka", "query": "summer+sky+clouds", "color": 0xD6EAF8},
          #  {"text": "🌴 Palmy w tle, odpowiedzi w cieniu", "query": "palm+trees+summer", "color": 0x52BE80},
         #   {"text": "🌊 Fale uderzają, powiadomienia leniwie spływają", "query": "ocean+waves+summer", "color": 0x5DADE2},
        #    {"text": "⛱️ Leżak gotowy, ping ignorowany", "query": "beach+chair+umbrella", "color": 0xF7DC6F},
       #     {"text": "🌻 Słoneczniki patrzą, użytkownicy nie", "query": "sunflower+field+summer", "color": 0xF1C40F},
      #      {"text": "🌈 Po deszczu memy wychodzą żywsze", "query": "rainbow+summer+rain", "color": 0xBB8FCE},
     #       {"text": "🌬️ Lekki wiatr = minimalna motywacja", "query": "summer+breeze", "color": 0x7FB3D5},
    #        {"text": "☀️ Okulary przeciwsłoneczne obowiązkowe przy tagach", "query": "sunglasses+summer+sun", "color": 0xF39C12},
   #         {"text": "🌅 Zachód słońca = czas refleksji nad Discordem", "query": "sunset+summer+beach", "color": 0xF5B041},
  #      ],
 #   },
#
   # "summer_chill": {
  #      "name": "Wakacje / chill",
 #       "items": [
#            {"text": "🏖️ Plaża w tle, powiadomień brak", "query": "beach+summer+relax", "color": 0x85C1E9},
           # {"text": "🍹 Koktajl w ręku, chaos na czacie", "query": "cocktail+summer+drink", "color": 0xEB984E},
          #  {"text": "🛶 Kajak gotowy, serwer w tle", "query": "kayak+lake+summer", "color": 0x5DADE2},
         #   {"text": "🎶 Muzyka wakacyjna = odpowiedzi minimalne", "query": "summer+music+vibes", "color": 0xAF7AC5},
        #    {"text": "🏄 Fala przychodzi, ping nie", "query": "surfing+wave+summer", "color": 0x48C9B0},
       #     {"text": "🌴 W cieniu palmy = tryb relaks", "query": "palm+shade+summer", "color": 0x52BE80},
      #      {"text": "🐚 Muszelki liczą powiadomienia, ja nie", "query": "seashells+beach", "color": 0xFAD7A0},
     #       {"text": "🕶️ Chill w pełnej krasie", "query": "summer+relax+sunglasses", "color": 0x566573},
    #        {"text": "🐠 Woda chłodzi, serwer też", "query": "underwater+fish+summer", "color": 0x5DADE2},
   #         {"text": "🌊 Szum morza = wymówka do braku aktywności", "query": "sea+waves+relax", "color": 0x3498DB},
  #      ],
 #   },
#
    #"summer_memes": {
   #     "name": "Humor / memy",
  #      "items": [
            #{"text": "🐳 Ping jak wieloryb – czasem dociera", "query": "whale+ocean+funny", "color": 0x5DADE2},
           # {"text": "🦀 Krab blokuje kanał, ja pod parasolem", "query": "crab+beach+funny", "color": 0xE74C3C},
          #  {"text": "🏖️ Plaża mówi: „Nie taguj mnie”", "query": "beach+funny+summer", "color": 0x85C1E9},
         #   {"text": "🐠 Ryba przemyka, powiadomień brak", "query": "fish+underwater+summer", "color": 0x5DADE2},
        #    {"text": "🌴 Palma przewraca memy na bok", "query": "palm+tree+funny", "color": 0x52BE80},
       #     {"text": "🐚 Muszle komentują w ciszy", "query": "seashell+macro+beach", "color": 0xFAD7A0},
      #      {"text": "🌊 Fala humoru rozbija powiadomienia", "query": "wave+ocean+funny", "color": 0x3498DB},
     #       {"text": "🐬 Delfin taguje przypadkowych użytkowników", "query": "dolphin+funny+ocean", "color": 0x85C1E9},
    #        {"text": "🐞 Biedronka wakacyjna = dopisek dnia", "query": "ladybug+summer", "color": 0xE74C3C},
   #         {"text": "🌞 Słońce świeci, chaos trwa", "query": "sunny+summer+chaos", "color": 0xF4D03F},
  #      ],
 #   },
#
#    "summer_food": {
     #   "name": "Lody / jedzenie letnie",
      #  "items": [
            #{"text": "🍉 Arbuz = obowiązkowy ping-break", "query": "watermelon+summer", "color": 0xE74C3C},
           # {"text": "🥤 Koktajl owocowy = minimalna produktywność", "query": "fruit+smoothie+summer", "color": 0xEB984E},
          #  {"text": "🌽 Grill gotowy, serwer w tle", "query": "bbq+grill+summer", "color": 0xDC7633},
         #   {"text": "🍍 Ananas patrzy na czat, ja nie", "query": "pineapple+summer", "color": 0xF4D03F},
        #    {"text": "🥪 Kanapka w ręku = wymówka do lenistwa", "query": "sandwich+summer+lunch", "color": 0xD5DBDB},
       #     {"text": "🧃 Sok z cytryny = detox powiadomień", "query": "lemon+juice+summer", "color": 0xF7DC6F},
      #      {"text": "🍓 Truskawki sezonowe = sezonowe dopiski", "query": "strawberries+summer", "color": 0xC0392B},
     #       {"text": "🍹 Drink w tle = serwer chill", "query": "summer+drink+cocktail", "color": 0xAF601A},
    #        {"text": "🥗 Sałatka w ręku, memy w tle", "query": "salad+healthy+summer", "color": 0x52BE80},
   #     ],
  #  },

 #   "summer_activity": {
#        "name": "Aktywność / ruch",
      #  "items": [
     #       {"text": "🏊 Basen gotowy, ping się kąpie", "query": "swimming+pool+summer", "color": 0x5DADE2},
    #        {"text": "🚴 Rower wyjechał, użytkownicy w trybie offline", "query": "cycling+summer", "color": 0x52BE80},
   #         {"text": "🏋️ Siłownia = wymówka do ignorowania tagów", "query": "gym+workout+summer", "color": 0x566573},
  #          {"text": "🛶 Kajak w ruchu, serwer w spokoju", "query": "kayak+river+summer", "color": 0x5DADE2},
          #  {"text": "🏖️ Spacer po plaży = minimalne działania", "query": "beach+walk+summer", "color": 0xFAD7A0},
         #   {"text": "🏌️ Golf + powiadomienia ignorowane", "query": "golf+field+summer", "color": 0x27AE60},
        #    {"text": "🏄 Surfing = chaos kontrolowany", "query": "surfing+wave", "color": 0x48C9B0},
       #     {"text": "🤸 Gimnastyka = codzienny dopisek", "query": "gymnastics+summer", "color": 0xAF7AC5},
      #      {"text": "🏹 Strzały w powietrzu = tagi nie dochodzą", "query": "archery+summer", "color": 0x935116},
     #       {"text": "🧗 Wspinaczka = mało powiadomień, dużo humoru", "query": "climbing+mountain+summer", "color": 0x7DCEA0},
    #    ],
   # },

  #  "summer_productivity": {
 #       "name": "Planowanie / produktywność w lato",
#        "items": [
         #   {"text": "📝 Lista rzeczy do zrobienia: wakacje trwają", "query": "to+do+list+summer", "color": 0x5D6D7E},
        #    {"text": "📅 Kalendarz mówi: „odpoczywaj”", "query": "calendar+summer+planning", "color": 0x5499C7},
       #     {"text": "🔄 Rotacja dopisków w trybie wakacyjnym", "query": "refresh+cycle+summer", "color": 0x48C9B0},
      #      {"text": "🏝️ Cel dnia: chill + minimalne działania", "query": "island+relax+summer", "color": 0x76D7C4},
     #       {"text": "💡 Pomysł: przerwa na drinka = obowiązkowa", "query": "summer+idea+drink", "color": 0xF8C471},
    #        {"text": "⏳ Czas płynie, serwer powoli", "query": "time+slow+summer", "color": 0x95A5A6},
   #         {"text": "🧭 Kompas pokazuje kierunek do basenu", "query": "compass+direction+pool", "color": 0x1ABC9C},
  #          {"text": "🏡 Widok z okna inspiruje, odpowiedzi nie", "query": "summer+window+view", "color": 0x52BE80},
 #           {"text": "🥶 Lód w drinku = produktywność schłodzona", "query": "ice+drink+summer", "color": 0x85C1E9},
        #    {"text": "🎯 Cel: przeżyć lato i nie odpowiadać na wszystko", "query": "summer+goal+relax", "color": 0x2874A6},
 #       ],
  #  },
#}

# CHRISTMAS_THEMES = {
 #   "autumn_nature": {
       # "name": "Liście i natura",
      #  "items": [
      #      {"text": "🍁 Liście spadają, a serwer w trybie chill", "query": "autumn+leaves+fall", "color": 0xD35400},
     #       {"text": "🌳 Drzewa patrzą, użytkownicy nie", "query": "autumn+trees+forest", "color": 0x196F3D},
    #        {"text": "🌬️ Wiatr przerzuca memy jak liście", "query": "wind+autumn+leaves", "color": 0x7D6608},
           # {"text": "🌰 Orzechy spadają, chaos rośnie", "query": "nuts+autumn+forest", "color": 0x6E2C00},
          #  {"text": "🍂 Dywan liści = naturalny filtr pingów", "query": "fallen+leaves+ground", "color": 0xBA4A00},
         #   {"text": "🌾 Mgła nad polem = mgła w powiadomieniach", "query": "fog+field+autumn", "color": 0xAAB7B8},
        #    {"text": "🌿 Zielono-żółto, serwer spokojny", "query": "autumn+green+yellow+leaves", "color": 0x7DCEA0},
       #     {"text": "🍁 Jesienne porządki = dopisek dnia", "query": "autumn+cleaning+yard", "color": 0xCA6F1E},
      #      {"text": "🌳 Widok z okna = spokój i refleksja", "query": "autumn+window+view", "color": 0x1E8449},
     #   ],
    #},

   # "autumn_weather": {
      #  "name": "Pogoda / chłód",
       # "items": [
      #      {"text": "🌧️ Deszcz uderza, powiadomienia spadają", "query": "rain+window+autumn", "color": 0x5DADE2},
     #       {"text": "🌬️ Wiatr hula, ja pod kocem", "query": "windy+autumn+weather", "color": 0x7FB3D5},
           # {"text": "🌫️ Mgła zakrywa odpowiedzi", "query": "fog+autumn+morning", "color": 0x95A5A6},
          #  {"text": "🧥 Kurtka gotowa, serwer w tle", "query": "jacket+autumn+outfit", "color": 0x566573},
         #   {"text": "☁️ Chmury = wymówka do minimalnej aktywności", "query": "cloudy+autumn+sky", "color": 0xD6EAF8},
        #    {"text": "🌦️ Płaszcz + parasol = produktywność w trybie slow", "query": "raincoat+umbrella+autumn", "color": 0x5DADE2},
       #     {"text": "🌂 Krople na szybie = naturalny alert", "query": "raindrops+window", "color": 0x3498DB},
      #      {"text": "🌨️ Pierwszy mróz = powód do kawy", "query": "frost+morning+autumn", "color": 0xAED6F1},
     #       {"text": "🍂 Liście wirują, memy też", "query": "leaves+falling+wind", "color": 0xCA6F1E},
    #        {"text": "🌫️ Cisza w kanałach = jesienny spokój", "query": "foggy+quiet+autumn", "color": 0x7B7D7D},
   #     ],
  #  },

 #   "autumn_memes": {
    #    "name": "Humor / memy",
        #"items": [
       #     {"text": "🎃 Halloween minęło, memy pozostały", "query": "halloween+after+party", "color": 0xAF601A},
      #      {"text": "🦉 Sowa patrzy, użytkownicy znikli", "query": "owl+night+autumn", "color": 0x5D6D7E},
     #       {"text": "🍁 Liść taguje przypadkowych ludzi", "query": "leaf+falling+funny", "color": 0xD35400},
            #{"text": "🐿️ Wiewiórka kradnie ping", "query": "squirrel+autumn+funny", "color": 0x6E2C00},
           # {"text": "🦇 Nietoperz = nieoczekiwany dopisek", "query": "bat+dark+autumn", "color": 0x17202A},
          #  {"text": "🥶 Mróz lekki, humor silny", "query": "cold+autumn+funny", "color": 0x85C1E9},
         #   {"text": "🐾 Zwierzak blokuje kanał, ja czekam", "query": "pet+autumn+funny", "color": 0x52BE80},
        #    {"text": "🌰 Orzechy lecą, powiadomienia wolno", "query": "nuts+falling+autumn", "color": 0x873600},
       #     {"text": "🕸️ Pajęczyna = filtr chaosu", "query": "spiderweb+autumn", "color": 0x7B7D7D},
      #      {"text": "☕ Kawa rozwiązuje większość dram", "query": "coffee+autumn+cozy", "color": 0x6E2C00},
     #   ],
    #},

   # "autumn_chill": {
      #  "name": "Chill / odpoczynek",
     #   "items": [
           # {"text": "🛋️ Kanapa w trybie jesienny relaks", "query": "cozy+sofa+autumn", "color": 0xA04000},
          #  {"text": "☕ Gorąca kawa w ręku, serwer w tle", "query": "coffee+cozy+autumn", "color": 0x6E2C00},
         #   {"text": "📖 Książka + koc = idealny dopisek", "query": "reading+book+blanket", "color": 0x5B2C6F},
        #    {"text": "🎶 Muzyka nastrojowa = powiadomienia ignorowane", "query": "music+cozy+autumn", "color": 0xAF7AC5},
       #     {"text": "🐶 Pies obok, chaos minimalny", "query": "dog+cozy+autumn", "color": 0x52BE80},
      #      {"text": "🧸 Pluszak w roli moderatora", "query": "teddy+bear+cozy", "color": 0xAF7AC5},
     #       {"text": "🌅 Zachód słońca = minimalna aktywność", "query": "autumn+sunset", "color": 0xF5B041},
    #        {"text": "🕯️ Światło świec = codzienny chill", "query": "candles+cozy+autumn", "color": 0xF8C471},
   #         {"text": "🏡 Widok z okna inspiruje, powiadomienia nie", "query": "window+autumn+cozy", "color": 0x52BE80},
  #          {"text": "🔔 Dzwonek w tle = nie moje powiadomienia", "query": "doorbell+home", "color": 0xA93226},
 #       ],
#    },

    #"autumn_food": {
   #     "name": "Jedzenie / ciepłe napoje",
  #      "items": [
 #           {"text": "☕ Herbata obowiązkowa przy pingach", "query": "tea+autumn+cozy", "color": 0xA569BD},
#            {"text": "🍫 Gorąca czekolada = produktywność schłodzona", "query": "hot+chocolate+autumn", "color": 0x6E2C00},
           # {"text": "🥧 Ciasto dyniowe = codzienny dopisek", "query": "pumpkin+pie+autumn", "color": 0xDC7633},
          #  {"text": "🍂 Jabłka pieczone w tle", "query": "baked+apples+autumn", "color": 0xCA6F1E},
         #   {"text": "🥪 Kanapka w ręku, memy w tle", "query": "sandwich+cozy+autumn", "color": 0xD5DBDB},
        #    {"text": "🥤 Gorący napój = wymówka do lenistwa", "query": "warm+drink+autumn", "color": 0xF8C471},
       #     {"text": "🍵 Matcha dla relaksu, powiadomienia ignorowane", "query": "matcha+tea+cozy", "color": 0x27AE60},
      #      {"text": "🥐 Śniadanie w tle = spokój w kanałach", "query": "breakfast+cozy+autumn", "color": 0xF5CBA7},
     #       {"text": "🍪 Ciasteczka = motywator dnia", "query": "cookies+autumn+cozy", "color": 0xB9770E},
    #        {"text": "🥛 Mleko + memy = combo jesieni", "query": "milk+cozy+autumn", "color": 0xFDFEFE},
   #     ],
  #  },

   # "autumn_productivity": {
  #      "name": "Planowanie / produktywność",
 #       "items": [
#            {"text": "📝 Lista rzeczy do zrobienia = minimalna aktywność", "query": "to+do+list+autumn", "color": 0x5D6D7E},
           # {"text": "📅 Kalendarz mówi: „jesień = wolniej”", "query": "calendar+autumn", "color": 0x5499C7},
          #  {"text": "🧭 Kompas pokazuje kierunek do kawy", "query": "compass+coffee", "color": 0x1ABC9C},
         #   {"text": "⏳ Czas leci, powiadomienia powoli", "query": "time+slow+autumn", "color": 0x95A5A6},
        #    {"text": "🔄 Rotacja dopisków w trybie spokojnym", "query": "refresh+cycle+calm", "color": 0x48C9B0},
       #     {"text": "🏡 Widok z okna inspiruje, odpowiedzi nie", "query": "window+autumn+view", "color": 0x52BE80},
      #      {"text": "💡 Pomysł dnia: chill + małe kroki", "query": "minimal+idea+autumn", "color": 0xF7DC6F},
     #       {"text": "🎯 Cel dnia: przetrwać jesień bez dram", "query": "goal+focus+autumn", "color": 0x2874A6},
    #        {"text": "🕰️ Plan dnia: kawa, książka, powiadomienia później", "query": "clock+coffee+book", "color": 0x7B7D7D},
   #         {"text": "🍁 Zbieranie liści = zbieranie energii na zimę", "query": "raking+leaves+autumn", "color": 0xCA6F1E},
  #      ],
 #   },
#}
session: aiohttp.ClientSession = None  # globalna sesja HTTP

async def send_christmas_embed(channel):
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(timeout=HTTP_TIMEOUT)


    key, category = random.choice(list(CHRISTMAS_THEMES.items()))
    item = random.choice(category["items"])

    text = item["text"]
    query = item["query"]
    color = item["color"]

    url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&page={random.randint(1,10)}"
    headers = {"Authorization": PEXELS_API_KEY}

    embed = discord.Embed(
    title=category["name"],
    description=text,
    color=color
    )

    for attempt in range(1, 4):
        try:
            async with session.get(url, headers=headers, timeout=15) as resp:
                status = resp.status
                if status != 200:
                    print(f"PEXELS: HTTP {status}. Próba {attempt}/3.")
                    # Po 3 próbach rezygnujemy
                    if attempt == 3:
                        await channel.send(embed=discord.Embed(
                            title="❌ Błąd Pexels",
                            description=f"Pexels zwrócił status {status}. Nie udało się pobrać zdjęcia.",
                            color=0xE74C3C))
                        return
                    else:
                        # czekamy 10 minut i spróbujemy ponownie
                        await asyncio.sleep(600)
                        continue

                data_json = await resp.json()
        except aiohttp.ClientError as e:
            print(f"PEXELS: wyjątek {e}. Próba {attempt}/3.")
            if attempt == 3:
                await channel.send(embed=discord.Embed(
                    title="❌ Błąd Pexels",
                    description=f"Nie udało się połączyć się z Pexels. {e}",
                    color=0xE74C3C))
                return
            else:
                await asyncio.sleep(600)
                continue

        photos = data_json.get("photos", [])
        if not photos:
            print("PEXELS: brak zdjęć dla zapytania.")
            if attempt == 3:
                await channel.send(embed=discord.Embed(
                    title="❌ Błąd Pexels",
                    description="Brak zdjęć dla danego zapytania. Operacja przerwana po 3 próbach.",
                    color=0xE74C3C))
                return
            else:
                await asyncio.sleep(600)
                continue

        # Wybieramy jedno zdjęcie i pobieramy obrazek
        photo = random.choice(photos)
        image_url = photo["src"]["large2x"]
        try:
            async with session.get(image_url, timeout=15) as img_resp:
                if img_resp.status != 200:
                    print(f"IMAGE: HTTP {img_resp.status}.")
                    if attempt == 3:
                        await channel.send(embed=discord.Embed(
                            title="❌ Błąd pobierania obrazka",
                            description=f"Pexels zwrócił status {img_resp.status} przy pobieraniu obrazka.",
                            color=0xE74C3C))
                        return
                    else:
                        await asyncio.sleep(600)
                        continue
                image_data = await img_resp.read()
        except aiohttp.ClientError as e:
            print(f"IMAGE: wyjątek {e}.")
            if attempt == 3:
                await channel.send(embed=discord.Embed(
                    title="❌ Błąd pobierania obrazka",
                    description=f"Nie udało się pobrać obrazka: {e}",
                    color=0xE74C3C))
                return
            else:
                await asyncio.sleep(600)
                continue

        file = discord.File(fp=io.BytesIO(image_data), filename="swieta.jpg")
        embed.set_image(url="attachment://swieta.jpg")
        await channel.send(embed=embed, file=file)
        return  

CHANNEL_ID = int(os.environ["CHANNEL_ID"])


active_games = set()

# Prawdziwa mapa kolorów ruletki amerykańskiej
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}


def get_roulette_color(n: int) -> str:
    if n == 0:
        return "🟩"
    elif n in RED_NUMBERS:
        return "🟥"
    else:
        return "⬛"


ROULETTE_COST = 40
JACKPOT_RESET = 10000


FAIL_RESPONSES = [
    "Fortuna ślepa, ty głuchy. Tragiczne połączenie.",
    "Ruletka cię nie lubi. Szczerze mówiąc, ja też trochę nie.",
    "Statystyki mówią: następnym razem też przegrasz. Ale próbuj.",
    "Koło się kręci, monety lecą. Twoje monety. Cudzym kierunku.",
    "Może następnym razem postaw na modlitwę zamiast zakładu.",
    "Matematyka: nieubłagana jak twoja przegrana.",
    "Kasjer ruletki śmieje się cicho. Bardzo cicho.",


    "To nie pech. To konsekwencja wyborów o wątpliwej jakości.",
    "Koło nie oszukuje. Ono tylko nie współpracuje z tobą.",
    "Wynik zapisany, zanim zdążyłeś mieć nadzieję.",
    "Ruletka zrobiła swoje. Ty zrobiłeś resztę błędów.",
    "Przegrana wpisana w model. Ty właśnie ją zainicjowałeś.",
    "Szczęście dziś nie loguje się na twoje konto.",
    "Monety właśnie zmieniły właściciela. Bez zgody.",
    "System działa poprawnie. Dla wszystkich oprócz ciebie.",
    "Nie przegrałeś z grą. Przegrałeś z matematyką.",
    "Koło uznało, że nie jesteś w jego planie wypłat.",
    "Zbyt pewny ruch. Zbyt przewidywalny wynik.",
    "Los odczytał twoją decyzję i się nie przejął.",
    "Ruletka nie ma emocji. Ty właśnie miałeś ich za dużo.",
    "Próbowałeś wygrać z rozkładem prawdopodobieństwa. Odważnie.",
    "To była krótka historia twoich monet.",
    "Zegar szczęścia cofnął się o kilka złych decyzji.",
    "Koło kręci się dalej. Ty już trochę mniej.",
    "Wynik: zgodny z oczekiwaniami systemu. Nie twoimi.",
    "Monety nie znikają. One zmieniają adres.",
    "Ruletka zanotowała twoją stratę bez emocji.",
    "Zbyt wiele nadziei jak na jeden spin.",
    "To był klasyczny przypadek 'prawie się udało'. Tyle że nie.",
    "System nie bugował się. Niestety.",
    "Zagrane. Rozliczone. Zapomniane przez saldo.",
    "Twoje monety właśnie przeszły na stronę ciemną.",
    "Niektóre wyniki są nieuniknione. Ten był jednym z nich.",
    "Ruletka nie potrzebuje szczęścia. Ty tak.",
    "Wynik nie był personalny. Ale wyglądał.",
    "Monety: w dół. Wiara: też w dół.",
    "Koło zakończyło dyskusję zanim się zaczęła.",
    "Nie ma tu miejsca na negocjacje z losem.",
    "Przegrana tak czysta, że aż matematyczna.",
    "Szczęście dziś było w trybie offline.",
    "To nie dramat. To statystyka w ruchu.",
]


WIN_RESPONSES = [
    "Przypadek? Talent? Głównie przypadek.",
    "Wygrałeś. Ruletka jest w szoku. My też.",
    "Koło łaskawe dziś. Nie przyzwyczajaj się.",
    "Monety wróciły. Jak pies do pana, tylko lepiej.",
    "Szczęście uśmiechnęło się. Brzydko, ale jednak.",
    "Wygrałeś. Statystyk płacze w kącie.",
]


JACKPOT_RESPONSES = [
    "JACKPOT. Zielone pole. Jeden na trzydzieści siedem. DLACZEGO TY.",
    "Zero. ZERO. Cała pula twoja. Ruletka chyba się zepsuła.",
    "Wygrałeś jackpota. Proszę nie mówić innym graczom, bo będą płakać.",
    "🟩 Zero. Złoty los. Astronomiczna głupota losu na twoją korzyść.",
]


ALLOWED_BETS = ["czerwone", "czarne", "zielone", "parzyste", "nieparzyste"]



@tasks.loop(hours=8)
async def christmas_loop():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await send_christmas_embed(channel)
        else:
            print(f"Nie znaleziono kanału o ID {CHANNEL_ID}")
    except Exception as e:
        print("❌ BŁĄD W christmas_loop:", repr(e))


WELCOME_CHANNEL_ID = int(os.environ["WELCOME_CHANNEL_ID"])

@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

    if channel:
        await channel.send(
            f"🎉 Witamy nowego członka: {member.mention}! Dajcie mu serduszko ❤️"
        )

@bot.event
async def on_message(message):
    # Ignoruj własne wiadomości
    if message.author == bot.user:
        return
    # W odpowiedzi na DM do bota
    if isinstance(message.channel, discord.DMChannel):
        await message.channel.send(
            "Cześć! Ja reaguję tylko na komendy zaczynające się od `?` wysłane na serwerze. Priv nie obsługuję. Spróbuj np. `?ping`"
        )
        return
    await bot.process_commands(message)


from discord.ext import commands

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        if ctx.author.id in active_games:
            return
        responses = [
            "🚫 Nie. Ta komenda nie istnieje.",
            "🤖 Przestań pisać losowe rzeczy.",
            "📵 Idź na spacer. Serio.",
            "🧠 To nie Minecraft, nie craftujesz komend.",
            "💀 Ta komenda nie żyje i nigdy nie istniała."
        ]
        await ctx.send(random.choice(responses))
        return


async def reflex_task(channel, delay: int):
    await asyncio.sleep(delay)
    reflex_state["active"] = True
    await channel.send("⚡ **TERAZ!** Pierwszy, kto wpisze `?caim reflex`, zgarnął 100 monet! 💰")
    await asyncio.sleep(30)
    if reflex_state["winner"] is None:
        reflex_state["active"] = False
        reflex_state["running"] = False
        await channel.send("⏳ Nikt nie zdążył. Event wygasł.")
    
# --- Bezpieczne zamknięcie globalnej sesji aiohttp przy wyłączeniu bota ---
@bot.event
async def on_disconnect():
    global session
    if session and not session.closed:
        await session.close()
        print("🌐 Globalna sesja aiohttp została zamknięta.")



EMOJI_POOL = ["🍒", "🍋", "🔔", "💎", "🍀", "🍇"]


DEAF_PROPHECIES = [
    "🔮 Przeznaczenie spojrzało… i przewróciło oczami.",
    "🌌 Los uznał, że to nie ta linia czasowa.",
    "🪐 Kosmos mówi: „meh” nie tym razem.",
    "✨ Gwiazdy się ustawiły… przeciwko tobie.",
    "🎲 Dziś nie wygrywasz. Nawet w Monopoly.",
    "🍀 Masz szczęście. Tylko nie dziś.",
    "⏭️ Wszechświat nacisnął „pomiń”, więc zagraj jeszcze raz.",
    "📉 System wykrył brak aury zwycięzcy.",
    "🎰 Automat stwierdził: próbuj później.",
    "🌑 Energia dnia: porażka deluxe.",

    "🌀 Rzeczywistość zrobiła unik.",
    "🚫 RNG mówi: absolutnie nie.",
    "📛 Twoje szczęście właśnie wyszło po mleko.",
    "🧊 Zimny los. Bardzo zimny.",
    "🎭 Wszechświat testuje twoją cierpliwość.",
    "📉 Kurs szczęścia spadł do zera.",
    "🔕 Dziś wyciszono twoje wygrane.",
    "🪦 Tu leży twoja passa zwycięstw.",
    "📦 Szczęście niedostarczone. Spróbuj jutro.",
    "🛑 System: brak autoryzacji na wygraną.",

    "🌫️ Mgła pecha nie ustępuje.",
    "🎯 Cel: wygrać. Wynik: nie tym razem.",
    "📉 Wykres szczęścia wygląda źle.",
    "🪙 Moneta by się od ciebie odwróciła.",
    "🧭 Kompas wskazuje kierunek: porażka.",
    "🔥 Spaliło się zanim zaczęło.",
    "🎧 Wszechświat nie słucha próśb.",
    "🧱 Trafiłeś na ścianę RNG.",
    "📴 Szczęście jest offline.",
    "🧃 Wypito twoją dawkę farta.",

    "🕳️ Wpadłeś w dziurę pecha.",
    "📭 Szczęście nie odebrało wiadomości.",
    "🔄 Spróbuj jeszcze raz. I jeszcze. I jeszcze.",
    "🪫 Poziom szczęścia: 0%.",
    "🎮 Game over, ale bez dramatu.",
    "📉 RNG ma dziś zły humor.",
    "🪤 Złapałeś się w pułapkę losu.",
    "🌋 Wulkan pecha wybuchł.",
    "🧊 Zamrożono twoją wygraną.",
    "📡 Brak sygnału szczęścia.",

    "🪶 Lekki powiew pecha.",
    "🎰 Automat: „nie dzisiaj, kolego”.",
    "📉 Twoje szanse właśnie wyszły z czatu.",
    "🧠 System myśli… i odrzuca.",
    "🪫 Energia zwycięstwa wyczerpana.",
    "🚷 Dostęp do wygranej zabroniony.",
    "🌪️ Wir pecha wciąga wszystko.",
    "📊 Statystyki mówią: spróbuj później.",
    "🧃 Sok z pecha świeżo wyciśnięty.",
    "🔮 Wizja przyszłości: dalej przegrywasz.",

    "📴 Serwer szczęścia nie odpowiada.",
    "🪦 Kolejna próba pochowana.",
    "🧩 Brakuje elementu: szczęścia.",
    "🎭 Los robi sobie żarty.",
    "🌌 Wszechświat: „to nie ten dzień”.",
    "🧊 Chłodna odmowa od RNG.",
    "📉 Szansa spadła przez podłogę.",
    "🪙 Nawet rzut monetą by cię zdradził.",
    "🚫 Ten timeline nie przewiduje wygranej.",
    "🎲 Spróbuj jeszcze raz. Dla sportu."
]


MINI_PROPHECIES = [
    "Przepowiadam Ci, że... Ktoś dziś zapyta o coś oczywistego.",
    "Przepowiadam Ci, że... Za godzinę przypomnisz sobie coś żenującego.",
    "Przepowiadam Ci, że... Twoja lodówka otworzy się przynajmniej raz.",
    "Przepowiadam Ci, że... Jutro też będzie jutro.",
    "Przepowiadam Ci, że... Herbata wystygnie szybciej niż planowałeś.",
    "Przepowiadam Ci, że... Ktoś powie „to tylko 5 minut” i nie będzie to 5 minut.",
    "Przepowiadam Ci, że... Dziś zjesz coś. To będzie jedzenie."
]


JACKPOT_PROPHECIES = [
    "Przepowiadam Ci, że... Twoje przeznaczenie ma opóźnienie, ale dziś nadrobi.",
    "Przepowiadam Ci, że... Jesteś główną postacią… przynajmniej przez chwilę.",
    "Przepowiadam Ci, że... Wszechświat mrugnął. To był znak.",
    "Przepowiadam Ci, że... Twoja legenda zacznie się dziś. Może.",
    "Przepowiadam Ci, że... Masz w sobie potencjał. Tym razem znaleziony.",
    "Przepowiadam Ci, że... Przyszły ty mówi: no, w końcu."
]



@bot.command(name="casino")
async def kasyno(ctx):
    user_id = ctx.author.id

    # 🔒 LIMIT 2 DZIENNIE
    count = get_casino_count(user_id)
    if count >= 2:
        await ctx.send(f"⏳ {ctx.author.mention}, wykorzystałeś już 2 wejścia do kasyna dziś.")
        return

    await ctx.send(
        "🎰 **Kasyno zostało aktywowane!**\n\n"
        "Zagraj o tajemniczą przepowiednię przyszłości!\n\n"
        f"Wybierz **3 emotki** z tej puli:\n{' '.join(EMOJI_POOL)}\n\n"
        "2 takie same = wygrana\n"
        "3 takie same = JACKPOT\n"
        "0 trafień = Kasyno nawet nie udaje współczucia\n\n"
        "⏳ Masz 1 minutę. Wyślij 3 emotki w jednej wiadomości."
    )

    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel


    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        await ctx.send("⏳ Kasyno się zamknęło. Los nie czeka na spóźnialskich.")
        return


    user_emojis = [c for c in msg.content if c in EMOJI_POOL]


    if len(user_emojis) != 3:
        await ctx.send("❌ Dokładnie 3 emotki. Kasyno nie negocjuje.")
        return


    # Dopiero tutaj – po udanej walidacji
    set_casino_count(user_id, count + 1)


    bot_emojis = [random.choice(EMOJI_POOL) for _ in range(3)]

    from collections import Counter
    user_count = Counter(user_emojis)
    bot_count = Counter(bot_emojis)


    matches = sum(
        min(user_count[emoji], bot_count[emoji])
        for emoji in EMOJI_POOL
    )

    if matches == 3:
        reward = 500
        prophecy = random.choice(JACKPOT_PROPHECIES)
        verdict = "💥 **JACKPOT!!!** 💥"

    elif matches == 2:
        reward = 100
        prophecy = random.choice(MINI_PROPHECIES)
        verdict = "✨ **WYGRANA!**"

    else:
        reward = -10
        prophecy = random.choice(DEAF_PROPHECIES)
        verdict = "💀 **PRZEGRANA.**"

    add_balance(user_id, reward)

    await ctx.send(
        f"🎲 **Twoje emotki:** {' '.join(user_emojis)}\n"
        f"🎰 **Kasyno:** {' '.join(bot_emojis)}\n\n"
        f"🎯 Trafienia: **{matches}/3**\n\n"
        f"{verdict}\n"
        f"💰 Zmiana balansu: **{reward:+} Monet Reputacji**\n"
        f"🔮 {prophecy}"
    )
    
PING_REPLIES = [
    "Pong! Ale czy naprawdę tego chciałeś?",
    "Twój ping został odnotowany przez Wszechświat. On też się zdziwił.",
    "Pong… ale serwer mówi „meh”",
    "Ping przyjęty. Twoje WiFi odetchnęło.",
    "Pong! Czy to znaczy, że jesteś produktywny? Nie sądzę.",
    "Twój ping odbił się echem w próżni. Pong!",
    "Otrzymano ping. Karma zareagowała obojętnie.",
    "Pong! Ale kot w biurze ignoruje cię.",
    "Serwer mrugnął. Ping zaliczony.",
    "Pong… a w twoim telefonie nic się nie zmieniło.",

    "Ping dotarł. Sens życia nadal nie.",
    "Pong! Serwer sprawdził – nadal żyjesz.",
    "Twoje kliknięcie miało konsekwencje. Oto one: Pong.",
    "Ping zaakceptowany. Wszechświat wzruszył ramionami.",
    "Pong! Zero nagród, zero emocji, czysta forma.",
    "Serwer odpowiedział. Ty dalej tutaj.",
    "Ping wykonany poprawnie. Gratulacje, to było łatwe.",
    "Pong! Twój router przez chwilę poczuł się potrzebny.",
    "Odebrano ping. Nic się nie zapaliło. Szkoda.",
    "Pong… ktoś gdzieś przewrócił oczami.",

    "Ping przeszedł. Twój plan na dzień nadal nie istnieje.",
    "Pong! System potwierdza: kliknąłeś przycisk.",
    "Twój ping został przetworzony z pełnym brakiem emocji.",
    "Pong! Serwer nawet nie udawał entuzjazmu.",
    "Ping dotarł szybciej niż twoje postanowienia.",
    "Pong! To było absolutnie konieczne, prawda?",
    "System zauważył ping. I tyle.",
    "Pong… echo odpowiedziało bardziej entuzjastycznie.",
    "Ping zaliczony. Wszechświat kontynuuje ignorowanie.",
    "Pong! Twój czas właśnie zniknął i nikt go nie widział.",

    "Ping dotarł. Odpowiedź była nieunikniona.",
    "Pong! Nic się nie zmieniło, ale przynajmniej próbowałeś.",
    "Twój ping został zaakceptowany przez rzeczywistość.",
    "Pong! Nawet serwer nie wie, po co to było.",
    "Ping wysłany. Sens nie dołączony.",
    "Pong! W tle coś się przeliczyło. Bez znaczenia.",
    "Ping odebrany. Cisza pozostała.",
    "Pong… system działa, ty też jakoś.",
    "Ping zaliczony. Motywacja nie.",
    "Pong! Serwer uznał to za wydarzenie dnia.",

    "Ping dotarł. Wszechświat nadal w trybie oszczędzania energii.",
    "Pong! Twój przycisk został naciśnięty z przekonaniem.",
    "Ping zaakceptowany. Logika nie zadawała pytań.",
    "Pong! Nawet bity się nie ucieszyły.",
    "Ping przeszedł. Historia tego nie zapamięta.",
    "Pong! Serwer przez sekundę udawał, że to ważne.",
    "Ping wykonany. Efekt: symboliczny.",
    "Pong… coś się wydarzyło. Technicznie.",
    "Ping dotarł. Twój dzień pozostaje taki sam.",
    "Pong! Minimum wysiłku, maksimum konsekwencji (czyli brak)."
]

CARDS_LIMIT = 3
CARDS_ENTRY_FEE = 30


# ===== PULE KART =====


BAD_CARDS = [
    {"name": "Złodziej", "emoji": "🦹", "val_range": (-90, -40), "desc": "Zniknąłeś na chwilę w tłumie. Twoja sakiewka też."},
    {"name": "Wielki Złodziej", "emoji": "🧛", "val_range": (-90, -40), "desc": "Zostałeś profesjonalnie oskubany w biały dzień."},
    {"name": "Kieszonkowiec", "emoji": "🤏", "val_range": (-90, -40), "desc": "Drobna ręka, duże ambicje. Twoje monety potwierdzają."},
    {"name": "Hazardzista", "emoji": "🎲", "val_range": (-90, -40), "desc": "Zabrał twoje monety i powiedział że to pożyczka. Skłamał."},
    {"name": "Fałszywy Prorok", "emoji": "🧙", "val_range": (-90, -40), "desc": "Obiecał fortunę. Dostarczył wyłącznie rozczarowanie."},
    {"name": "Lichwiarz", "emoji": "💀", "val_range": (-90, -40), "desc": "Odsetki policzone z góry. Ty o tym nie wiedziałeś."},
    {"name": "Demon Długów", "emoji": "😈", "val_range": (-90, -40), "desc": "Wyciągnął rachunek którego nie zamawiałeś."},
    {"name": "Czarny Kot", "emoji": "🐈‍⬛", "val_range": (-90, -40), "desc": "Przeszedł ci przez drogę. Portfel to poczuł."},
    {"name": "Podatek Losu", "emoji": "📜", "val_range": (-90, -40), "desc": "Universum wystawiło fakturę. Płatne natychmiast."},
    {"name": "Fałszywy Przyjaciel", "emoji": "🤝", "val_range": (-90, -40), "desc": "Uśmiechnął się ciepło odchodząc z twoimi monetami."},
    {"name": "Przekleństwo Wiedźmy", "emoji": "🧹", "val_range": (-90, -40), "desc": "Nie pamiętasz kiedy ją obraziłeś. Ona pamięta."},
    {"name": "Zły Bliźniak", "emoji": "👥", "val_range": (-90, -40), "desc": "Wziął twoje pieniądze i powiedział że to ty jesteś tym złym."},
    {"name": "Bankrut", "emoji": "📉", "val_range": (-90, -40), "desc": "Inwestycja nie wyszła. Twoja inwestycja w tę kartę."},
    {"name": "Karczmarz", "emoji": "🍺", "val_range": (-90, -40), "desc": "Rachunek okazał się wyższy niż menu sugerowało."},
    {"name": "Paserka", "emoji": "🛍️", "val_range": (-90, -40), "desc": "Kupiłeś coś czego nie widziałeś. Okazja stulecia. Nie."},
    {"name": "Fałszywy Medyk", "emoji": "💊", "val_range": (-90, -40), "desc": "Diagnoza: pusta kieszeń. Lekarstwo: brak."},
    {"name": "Pirat", "emoji": "🏴‍☠️", "val_range": (-90, -40), "desc": "Arrr. Twoje monety teraz pływają gdzie indziej."},
    {"name": "Kolektor Dusz", "emoji": "⚰️", "val_range": (-90, -40), "desc": "Nie zabrał duszy. Tylko monety. Uznaj to za sukces."},
    {"name": "Zły Czar", "emoji": "🌑", "val_range": (-90, -40), "desc": "Ktoś mruknął pod nosem i twój portfel odczuł konsekwencje."},
    {"name": "Smog Pechowy", "emoji": "🌫️", "val_range": (-90, -40), "desc": "Niewidzialny, nieuchwytny. Monety jednak bardzo uchwycił."},
    {"name": "Wróżka Bankructwa", "emoji": "🧚", "val_range": (-90, -40), "desc": "Machała różdżką radośnie. Twoje konto mniej radośnie."},
    {"name": "Nekromanta Długów", "emoji": "💀", "val_range": (-90, -40), "desc": "Wskrzesił twoje stare błędy finansowe. Razem z odsetkami."},
    {"name": "Kosmita Złodziej", "emoji": "👽", "val_range": (-90, -40), "desc": "Przyleciał z daleka specjalnie po twoje monety. Skuteczny."},
    {"name": "Kapitan Pecha", "emoji": "⚓", "val_range": (-90, -40), "desc": "Zabrał cię w rejs bez powrotu. Portfela przynajmniej."},
    {"name": "Widmo Straty", "emoji": "👻", "val_range": (-90, -40), "desc": "Niewidzialne. Bezgłośne. Bardzo kosztowne."},
    {"name": "Karciana Pułapka", "emoji": "🪤", "val_range": (-90, -40), "desc": "Wyglądała niewinnie. Kłamała."},
    {"name": "Zepsuty Talizman", "emoji": "🧿", "val_range": (-90, -40), "desc": "Miał chronić. Zapomniał po drodze."},
    {"name": "Plotkarz", "emoji": "🗣️", "val_range": (-90, -40), "desc": "Rozgłosił twoje finanse. Zainteresował tym złodziei."},
    {"name": "Zły Bard", "emoji": "🎸", "val_range": (-90, -40), "desc": "Śpiewał balladę o twojej stracie. Z wyprzedzeniem."},
    {"name": "Fałszywy Skarbnik", "emoji": "🏦", "val_range": (-90, -40), "desc": "Powiedział że przechowa monety. Przechowuje. U siebie."},
    {"name": "Alchemik Pecha", "emoji": "⚗️", "val_range": (-90, -40), "desc": "Zamienił twoje złoto w żal. To też jest alchemia."},
    {"name": "Czarny Rynek", "emoji": "🖤", "val_range": (-90, -40), "desc": "Transakcja sfinalizowana. Niekorzystnie dla ciebie."},
    {"name": "Pusty Skarb", "emoji": "📦", "val_range": (-90, -40), "desc": "Skrzynka wyglądała obiecująco. Była szczerze pusta."},
    {"name": "Manekwi Szczęścia", "emoji": "🪆", "val_range": (-90, -40), "desc": "Każda warstwa to kolejna strata. Aż do środka."},
    {"name": "Zły Horoskop", "emoji": "♑", "val_range": (-90, -40), "desc": "Gwiazdy powiedziały nie. Ty nie słuchałeś gwiazd."},
    {"name": "Przekupiony Sędzia", "emoji": "⚖️", "val_range": (-90, -40), "desc": "Wyrok zapadł zanim usiadłeś. Kara finansowa."},
    {"name": "Cień Przeszłości", "emoji": "🌘", "val_range": (-90, -40), "desc": "Dawny dług wrócił z odsetkami i złym humorem."},
    {"name": "Fałszywy Orakul", "emoji": "🔮", "val_range": (-90, -40), "desc": "Przepowiednia była trafna. Trafnie zła."},
    {"name": "Czarna Owca", "emoji": "🐑", "val_range": (-90, -40), "desc": "Sama obecność tej karty coś kosztuje. Właśnie zapłaciłeś."},
    {"name": "Szalbierz", "emoji": "🎩", "val_range": (-90, -40), "desc": "Wyjął monetę z twojego ucha. Nie oddał."},
]


GOOD_CARDS = [
    {"name": "Lekarz", "emoji": "🩺", "val_range": (100, 250), "desc": "Znalazł w kieszeni fartucha zapomniany banknot. Dał ci."},
    {"name": "Szczodry Kupiec", "emoji": "🛒", "val_range": (100, 250), "desc": "Pomylił cię z kimś ważnym. Zapłacił. Nie wyprowadzaj go z błędu."},
    {"name": "Błogosławieństwo", "emoji": "✨", "val_range": (100, 250), "desc": "Coś dobrego wydarzyło się bez wyraźnej przyczyny. Nie pytaj."},
    {"name": "Znalezisko", "emoji": "💰", "val_range": (100, 250), "desc": "Ktoś zgubił. Ty znalazłeś. Los działa dziś na twoją korzyść."},
    {"name": "Dobry Duch", "emoji": "👼", "val_range": (100, 250), "desc": "Zjawił się, zostawił monety, odszedł bez słowa. Klasyk."},
    {"name": "Starożytna Moneta", "emoji": "🪙", "val_range": (100, 250), "desc": "Antykwariusz zapłacił bez targowania. Podejrzane, ale bierzesz."},
    {"name": "Wróżka Szczęścia", "emoji": "🧚‍♀️", "val_range": (100, 250), "desc": "Machała różdżką w twoją stronę. Tym razem zadziałało."},
    {"name": "Łut Szczęścia", "emoji": "🍀", "val_range": (100, 250), "desc": "Jeden na milion. Statystycznie powinieneś grać w totka."},
    {"name": "Zapomniany Testament", "emoji": "📋", "val_range": (100, 250), "desc": "Ktoś o tobie pamiętał. Zaskakująco hojnie."},
    {"name": "Dobry Omen", "emoji": "🌟", "val_range": (100, 250), "desc": "Wszechświat kiwnął głową. Twój portfel to poczuł."},
    {"name": "Złota Rybka", "emoji": "🐟", "val_range": (100, 250), "desc": "Życzenie spełnione zanim zdążyłeś je wypowiedzieć."},
    {"name": "Łaskawy Los", "emoji": "🎯", "val_range": (100, 250), "desc": "Trafiony. Zatopiony. Ale w pozytywnym sensie."},
    {"name": "Dar Niebios", "emoji": "☁️", "val_range": (100, 250), "desc": "Spadło z nieba. Dosłownie nie wiesz jak. Bierz i milcz."},
    {"name": "Sprawiedliwy Trybunał", "emoji": "⚖️", "val_range": (100, 250), "desc": "Wreszcie ktoś przyznał ci rację. I dopłacił za kłopot."},
    {"name": "Szczęśliwy Traf", "emoji": "🎰", "val_range": (100, 250), "desc": "Jedyny raz kiedy los się pomylił na twoją korzyść."},
]


@bot.command()
async def ping(ctx):
    try:
        reply = random.choice(PING_REPLIES)
        await ctx.send(f"{ctx.author.mention} – {reply}")
    except Exception as e:
        print(f"[ping] {e}")
        await ctx.send("Wystąpił błąd podczas pingowania bota.")
        
# -------- Komendy moderacji i narzędzi --------
@bot.command()
async def warn(ctx, member: discord.Member, *, reason: str = "Brak powodu"):

    # --- sprawdzenie uprawnień ---
    if ctx.author.id not in MODERATORS:
        embed = discord.Embed(
            description="Nie masz uprawnień do użycia tej komendy.",
            color=0x95A5A6
        )
        await ctx.send(embed=embed)
        return

    # --- właściwa logika ---
    message_text = f"Gracz {member.mention} został ostrzeżony.\n{reason}"

    embed = discord.Embed(
        description=message_text,
        color=0xE74C3C
    )

    await ctx.send(embed=embed)

    # DM tylko dla ludzi
    if not member.bot:
        try:
            await member.send(message_text)
        except discord.Forbidden:
            await ctx.send("Nie mogę wysłać DM do tego użytkownika.")

@bot.command()
async def mute(ctx, member: discord.Member, *, reason: str = "Brak powodu"):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie masz uprawnień do tej komendy!")
        return
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Rola **Muted** nie istnieje.")
        return
    await member.add_roles(muted_role)
    await ctx.send(f"🔇 {member.name} został wyciszony. Powód: {reason}")

@bot.command()
async def unmute(ctx, member: discord.Member):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie masz uprawnień do tej komendy!")
        return
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Rola **Muted** nie istnieje.")
        return
    try:
        await member.remove_roles(muted_role)
        await ctx.send(f"{member.name} został odciszony.")
    except discord.HTTPException:
        await ctx.send("Nie mogę odciszyć tego użytkownika.")

@bot.command()
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie masz wymaganych uprawień!")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member.name} został wyrzucony. ({reason})")
    except discord.Forbidden:
        await ctx.send("Nie mam uprawnień, by wyrzucić tego użytkownika. Ma za wysoką rangę.")
    except discord.HTTPException:
        await ctx.send("Nie udało się wyrzucić tego użytkownika.")

@bot.command()
async def roll(ctx, guess: int):
    user_id = ctx.author.id

    # limit 4 dziennie
    count = get_roll_count(user_id)
    if count >= 4:
        await ctx.send(f"⏳ {ctx.author.mention}, wykorzystałeś już 4 rzuty dziś.")
        return

    set_roll_count(user_id, count + 1)

    # K20
    result = random.randint(1, 20)
    if not (1 <= guess <= 20):
        await ctx.send("❌ Podaj liczbę od 1 do 20.")
        return
    # trafienie
    if guess == result:
        add_balance(user_id, 1000)

        await ctx.send(
            f"🎲 Wybrałeś **{guess}**.\n"
            f"🧠 Wyrzuciłem **{result}**.\n\n"
            f"🏆 TRAFIŁEŚ! +1000 Monet Reputacji 💰"
        )
    else:
        add_balance(user_id, -50)

        await ctx.send(
            f"🎲 Wybrałeś **{guess}**.\n"
            f"🧠 Wyrzuciłem **{result}**.\n\n"
            f"💀 Pudło. -50 Monet Reputacji."
        )

@bot.command()
async def spamshield(ctx, member: discord.Member, times: int = 5):
    """Spamuje DM o tarczy do wskazanego gracza (domyślnie 5 razy, max 10)."""
    times = max(1, min(times, 10))
    sent = 0
    for _ in range(times):
        try:
            await member.send("🛡️ Użyj tarczy! Wróg nadciąga!")
            sent += 1
        except discord.Forbidden:
            await ctx.send(f"❌ Nie mogę wysłać wiadomości do {member.name}.")
            return
    await ctx.send(f"✅ Wysłałem {sent} ostrzeżeń do {member.mention} na priv.")

@bot.command()
async def important(ctx, *, message: str):
    content = ctx.message.content
    if not ctx.message.mentions and not ctx.message.role_mentions and "@everyone" not in content:
        await ctx.send("Musisz oznaczyć gracza, rolę lub użyć @everyone.")
        return
        

    notified = set()

    # Użytkownicy wymienieni bezpośrednio
    for member in ctx.message.mentions:
        if member.id == bot.user.id:
            continue
        try:
            await member.send(f"🔔 Masz nową ważną wiadomość! Przeczytaj ją teraz! **{ctx.guild.name}**: {message}")
            notified.add(member)
        except discord.Forbidden:
            await ctx.send(f"Nie mogę wysłać wiadomości do {member.name}.")
            

    # Użytkownicy z oznaczonych ról
    for role in ctx.message.role_mentions:
        for member in role.members:
            if member.bot:
                continue
            try:
                await member.send(f"🔔 Ważna wiadomość dla roli **{role.name}**: {message}")
                notified.add(member)
            except discord.Forbidden:
                await ctx.send(f"Nie mogę wysłać wiadomości do {member.name}.")

                # @everyone
    if "@everyone" in content:
        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                await member.send(f"🔔 Masz nową ważną wiadomość! Przeczytaj ją teraz!: {message}")
                notified.add(member)
            except discord.Forbidden:
                continue

    if notified:
        await ctx.send(f"✅ Wysłałem {len(notified)} do użytkowników wiadomości oznaczone jako **ważne**.")

@bot.command()
async def shield(ctx, member: discord.Member):
    """Informuje gracza o braku tarczy."""
    try:
        await ctx.send(f"{member.mention}, gracz został poinformowany o braku tarczy.")
        await member.send("🛡️ Użyj tarczy! Wróg już nadciąga!")
    except discord.Forbidden:
        await ctx.send("Nie mogę wysłać PW do tego użytkownika.")

@bot.command()
async def coinflip(ctx, choice: str):
    user_id = ctx.author.id

    choice = choice.lower()

    if choice not in ["orzeł", "reszka"]:
        await ctx.send("❌ Użyj: `?coinflip orzeł` albo `?coinflip reszka`.")
        return

    # limit 2 gry dziennie
    count = get_coinflip_count(user_id)
    if count >= 2:
        await ctx.send(f"⏳ {ctx.author.mention}, wykorzystałeś już 2 coinflipy dziś.")
        return

    set_coinflip_count(user_id, count + 1)

    result = random.choice(["orzeł", "reszka"])

    await ctx.send(f"🪙 Wypadło: **{result}**")

    if choice == result:
        reward = 30
        add_balance(user_id, reward)

        await ctx.send(
            f"🎉 WYGRAŁEŚ!\n"
            f"+30 Monet Reputacji 💰"
        )
    else:
        reward = -30
        add_balance(user_id, reward)

        await ctx.send(
            f"💀 PRZEGRANA.\n"
            f"{reward} Monet Reputacji"
        )

SARCASM_RESPONSES = [
    "✅ Tak — ale nie licz na to bez cudu.",
    "❌ Nie — chyba że znajdziesz jednorożca.",
    "🤷 Może. Albo nie. Zależy od twojej kolejki życzeń.",
    "🔁 Spróbuj jeszcze raz. I przestań wierzyć w bajki.",
    "🎲 Szanse: mniejsze niż półfinał w totka.",
    "🔥 Tak — kiedy świat się najpierw spali.",
    "💤 Nie teraz. Spróbuj za sto lat.",
    "🧊 Raczej nie, ale ładnie zabrzmiało to pytanie.",
    "🌪️ Tak — jeśli najpierw spadną gwiazdy z nieba.",
    "🪄 Pewnie, w jakiejś alternatywnej rzeczywistości.",
    "🏆 Tak — jeśli opanujesz teleportację najpierw.",
    "🧯 Nie; lepiej kup sobie gaśnicę nadziei.",
    "⚖️ 50/50 — rzuć monetą i przestań pytać bota.",
    "💩 Nie. I tak to pachnie porażką.",
    "🦄 Może — po oswojeniu jednorożca.",
    "📉 Statystyki krzyczą: nie.",
    "📈 Tak — jak tylko nauczysz się oszukiwać los.",
    "🔋 Brakuje energii wszechświata na to, więc nie teraz.",
    "🕰️ Może kiedyś. Tylko nie dziś i nie jutro.",
    "🪤 Nie daj się złapać na obietnice.",
    "🎭 Tak, ale to będzie spektakl żałosny.",
    "📞 Odbiornik nie odpowiada. Spróbuj później.",
    "🎁 Może, ale najpierw rozpakuj rzeczy.",
    "🧨 Nie — mamy na to dowód i raport.",
    "🧪 Wyniki eksperymentu: brak potwierdzenia.",
    "🧿 Los patrzy w bok — więc... raczej nie.",
    "🌧️ Deszcz szans na to: sporadyczny.",
    "🌈 Tak — po przejściu po tęczy.",
    "🚪 Drzwi do odpowiedzi są zamknięte. Klucz zgubiono.",
    "🪦 Nie. Spuść zasłonę nad tym marzeniem.",
    "🪙 Rzuć monetą — odpowiedź już padła.",
    "🦶 Twoje kroki prowadzą ku 'nie'.",
    "🍀 Niestety szczęście dziś na urlopie.",
    "🧵 Nitka losu jest przerwana więc brak odpowiedzi — sorry.",
    "🪵 Pal licho — czyli nie.",
    "🔧 Możliwe, jeśli potrafisz składać cuda.",
    "🌜Księżyc milczy — więc odpowiedź niepewna.",
    "📦 Odesłane bez śladu — brak sukcesu.",
    "📣 Tak — ale nikt tego nie usłyszy.",
    "🪞 Spójrz w lustro: tam jest odpowiedź.",
    "🎚️ Ustawienie domyślne: 'nie'.",
    "🔭 Widok jest mglisty — powtórz pytanie później.",
    "🎨 Tak, jeśli pomalujesz marzenia na zielono.",
    "🧙‍♂️ Czarnoksiężnik mówi: spróbuj jeszcze raz.",
    "🪄 Magia dziś na przerwie — raczej nie.",
    "🎯 Szansa jest, ale nie licz na celność.",
    "🤔 Może. A może nie. Życie.",
    "🌓 To zależy od fazy księżyca i Twoich decyzji życiowych.",
    "🥶 Zapytaj lodówkę. Ona wie więcej.",
    "🐱 Zapytałem i kot odpowiedział, że tak. Nie pytaj gdzie znalazłem kota.",
    "🕹️ Gra mówi nie: resetuj i spróbuj ponownie."
]


DAILY_MESSAGES = [
    "💸 Odbierasz wypłatę za bycie obecnym. Imponujące.",
    "🪙 System nagradza twoją egzystencję. Gratulacje.",
    "💰 Dostajesz monety za… no, oddychanie chyba.",
    "📦 Dzienna paczka odebrana. Nie pytaj skąd to się bierze.",
    "🤑 Kapitalizm działa nawet na Discordzie.",
    "🎁 Kolejna nagroda. Nadal nie wiadomo za co.",
    "💸 10 monet wpada. Nie przyzwyczajaj się.",
    "🏦 System uznał, że zasługujesz. Dziwne, ale ok.",
    "💰 Monety dodane. Twoje życie ma sens. Przynajmniej tutaj.",
    "🎉 Daily odebrane. Możesz wrócić jutro po więcej złudzeń.",

    "🪙 Gratulacje, system cię zauważył. Rzadkie zjawisko.",
    "💸 Dostajesz kasę za logowanie. Brzmi jak sen, co?",
    "📅 Kolejny dzień, kolejne monety. Rutyna piękna rzecz.",
    "💰 +10 monet. System wierzy w ciebie bardziej niż ty.",
    "🎁 Prezent dzienny. Bez okazji, bez sensu, ale jest.",
    "🤑 Twoje konto właśnie utyło o 10 monet.",
    "🏦 Wpłata przyjęta. Bank nie pyta o źródło.",
    "💸 Odbierasz nagrodę. Minimalny wysiłek, maksymalny efekt.",
    "🎉 System mówi: dobra robota. Za co? Nie wiadomo.",
    "💰 Monety przyznane. Kontynuuj… cokolwiek robisz.",

    "🪙 Oto twoje codzienne złudzenie progresu.",
    "💸 Dostajesz kasę za obecność. Bare minimum zaliczone.",
    "📦 Paczka dnia dostarczona. Bez podpisu.",
    "💰 +10 monet. Twój wkład pozostaje tajemnicą.",
    "🎁 Daily drop. RNG sprzyja… zawsze.",
    "🤑 Wpływ środków od nieznanego sponsora.",
    "🏦 System działa. Ty też jakoś działasz.",
    "💸 Nagroda odebrana. Możesz udawać produktywność dalej.",
    "🎉 Kolejny dzień przeżyty. System to docenia.",
    "💰 Monety dodane. Inflacja nadchodzi.",

    "🪙 Twoje daily. Bez fajerwerków, ale działa.",
    "💸 System rzucił ci 10 monet. Łap.",
    "📅 Logowanie zaliczone. Nagroda przyznana.",
    "💰 +10 monet. W sam raz na złe decyzje.",
    "🎁 Paczka odebrana. Zawartość: rozczarowanie i monety.",
    "🤑 Konto rośnie. Ego zaraz też.",
    "🏦 Bank znowu cię nie zignorował.",
    "💸 Odbiór nagrody zakończony sukcesem.",
    "🎉 System: 'proszę bardzo'.",
    "💰 Monety wpłynęły. Użyj ich źle.",

    "🪙 Gratulacje. Nadal tu jesteś.",
    "💸 Odbierasz wypłatę za konsekwencję. Szokujące.",
    "📦 Kolejna skrzynka dnia. Bez lootboxów, przykro mi.",
    "💰 +10 monet. Minimalizm finansowy.",
    "🎁 Daily claim complete. Achievement unlocked: rutyna.",
    "🤑 Pieniądze pojawiły się magicznie. Nie pytaj.",
    "🏦 System nie zapomniał o tobie. Jeszcze.",
    "💸 Nagroda przyznana. Idź ją stracić.",
    "🎉 Kolejny checkpoint życia zaliczony.",
    "💰 Monety dodane. Czas je przepalić.",

    "🪙 Dzienna dawka dopaminy dostarczona.",
    "💸 Odbierasz swoje 10 monet. Klasyka gatunku.",
    "📅 System odnotował twoje istnienie.",
    "💰 +10 monet. Ekonomia rośnie, sens maleje.",
    "🎁 Nagroda dnia. Nic specjalnego, ale działa.",
    "🤑 Konto powoli puchnie. Nie ekscytuj się.",
    "🏦 Wpłata zatwierdzona. Bez pytań.",
    "💸 Kolejna wypłata. Nadal za darmo.",
    "🎉 System nagradza lojalność. Albo nudę.",
    "💰 Monety przyznane. Witaj w pętli."
]

CRIME_LIST = [
    "Okraść sklep spożywczy",
    "Zhakować bank",
    "Ukraść pizzę z dostawy",
    "Podmienić ceny w supermarkecie",
    "Przejąć konto influencera",
    "Oszukać automat z napojami",
    "Włamać się do sejfu w biurze",
    "Zwinąć rower bez właściciela",
    "Przechytrzyć kasyno online",
    "Podszyć się pod urzędnika",
    "Wyłudzić darmową kebabową promocję",
    "Złamać system lojalnościowy sklepu",
    "Ukraść hot-doga z imprezy",
    "Zamienić etykiety produktów",
    "Oszukać bankomat na 10 zł",
    "Włamać się do lodówki sąsiada",
    "Przechwycić przesyłkę kurierską",
    "Zhakować system punktów w grze",
    "Podmienić playlistę w radiu",
    "Zrobić fake refund w sklepie",
    "Przejąć automat vendingowy",
    "Oszukać kasę samoobsługową",
    "Zwinąć ciasteczka z kuchni NPC",
    "Włamać się do systemu pizzy",
    "Podrobić kupon rabatowy",
    "Zhakować skrzynkę mailową (legalnie w grze oczywiście)",
    "Przechytrzyć ochronę sklepu",
    "Ukraść paczkę przed drzwiami",
    "Zamienić portfel NPC",
    "Zorganizować 'legalnie nielegalny' deal"
]

@bot.command(
    name="8ballfun",
    aliases=["ballfun", "🎱fun"]
)
async def eightballfun(ctx, *, question: str):
    """Sarkastyczny 8ball — odpowiedzi pasujące do pytań tak/nie."""
    answer = random.choice(SARCASM_RESPONSES)
    await ctx.send(f"**{ctx.author.display_name} pyta:** {question}\n{answer}")
    
@bot.command(name="daily")
async def daily(ctx):
    user_id = ctx.author.id
    loop = asyncio.get_event_loop()
    if not await async_can_claim_daily(user_id):
        await ctx.send(f"⏳ {ctx.author.mention}, już odebrałeś daily. Spróbuj jutro.")
        return
    reward = 10
    await loop.run_in_executor(None, claim_daily, user_id, reward)
    message = random.choice(DAILY_MESSAGES)
    await ctx.send(f"{message}\n\n💰 +{reward} Monet Reputacji dla {ctx.author.mention}")
    
@bot.command(name="saldo")
async def saldo(ctx):
    user_id = ctx.author.id

    balance = get_balance(user_id)

    await ctx.send(f"💰 {ctx.author.mention}, masz **{balance} Monet Reputacji**.")
    
@bot.command()
async def rps(ctx, choice: str):
    user_id = ctx.author.id

    choices = ["kamień", "papier", "nożyce"]

    choice = choice.lower()

    if choice not in choices:
        await ctx.send("Użyj: `?rps kamień`, `?rps papier` albo `?rps nożyce`.")
        return

    # limit 5 gier dziennie
    count = get_rps_count(user_id)
    if count >= 5:
        await ctx.send(f"⏳ {ctx.author.mention}, wykorzystałeś już 5 gier RPS dziś.")
        return

    set_rps_count(user_id, count + 1)

    bot_choice = random.choice(choices)

    # wynik
    if choice == bot_choice:
        result_text = "Remis!"
        delta = 0

    elif (choice == "kamień" and bot_choice == "nożyce") or \
         (choice == "papier" and bot_choice == "kamień") or \
         (choice == "nożyce" and bot_choice == "papier"):
        result_text = "Wygrałeś! 🎉"
        delta = 30

    else:
        result_text = "Przegrałeś! 😢"
        delta = -10

    # ekonomia
    add_balance(user_id, delta)

    await ctx.send(
        f"✊ Ty: **{choice}** | Bot: **{bot_choice}**\n"
        f"👉 {result_text}\n"
        f"{'💰 +' if delta > 0 else '💸 ' if delta < 0 else '➖ '} {abs(delta)} Monet Reputacji"
    )

@bot.command()
async def cat(ctx):
    url = "https://api.thecatapi.com/v1/images/search"
    try:
        async with aiohttp.ClientSession() as temp_session:
            async with temp_session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    image_url = data[0]["url"]
                    embed = discord.Embed(title="🐱 Znalazłem jednego!", color=0xFF9900)
                    embed.set_image(url=image_url)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("😿 Nie udało się znaleźć kota, spróbuj ponownie później!")
    except Exception as e:
        print(f"[cat] {e}")
        await ctx.send("😿 Wystąpił błąd podczas pobierania zdjęcia kota.")

@bot.command()
async def dog(ctx):
    url = "https://dog.ceo/api/breeds/image/random"
    try:
        async with aiohttp.ClientSession() as temp_session:
            async with temp_session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    image_url = data["message"]

                    embed = discord.Embed(title="🐶 Proszę, pies!", color=0x00AAFF)
                    embed.set_image(url=image_url)

                    await ctx.send(embed=embed)
                else:
                    await ctx.send("🐶 Pies się schował. Klasyka.")
    except Exception as e:
        print(f"[dog] {e}")
        await ctx.send("🐶 Coś się zepsuło przy pobieraniu psa.")

# --- Komendy pomocy i informacyjne ---

@bot.command(name="print")
async def cmd_print(ctx, *, text: str):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(text)

reflex_state = {
    "active": False,
    "winner": None,
    "running": False  # czy task już istnieje
}


@bot.command(name="reflex")
async def reflex(ctx):
    user_id = ctx.author.id


    used = get_reflex_used(user_id)
    if used >= 1:
        await ctx.send(f"⏳ {ctx.author.mention}, już dziś grałeś w reflex.")
        return


    if reflex_state["running"]:
        await ctx.send("⚡ Event reflex już jest aktywny. Czekaj na sygnał!")
        return  # nie zużywa daily


    set_reflex_used(user_id, 1)
    reflex_state["running"] = True
    reflex_state["active"] = False
    reflex_state["winner"] = None


    delay = random.randint(10, 3600)
    await ctx.send(
        "⚡ **REFLEX STARTOWANY**\n"
        "Za chwilę (do 1h) pojawi się: **TERAZ!**\n"
        "Kto pierwszy wpisze `?caim reflex` zgarnia 100 Monet Reputacji 💰"
    )
    asyncio.create_task(reflex_task(ctx.channel, delay))



@bot.command(name="caim")
async def caim(ctx, arg=None):
    if arg != "reflex":
        return


    if not reflex_state["active"]:
        await ctx.send("❌ Za wcześnie albo po evencie.")
        return


    if reflex_state["winner"] is not None:
        await ctx.send("❌ Ktoś był szybszy.")
        return


    reflex_state["winner"] = ctx.author.id
    reflex_state["active"] = False
    reflex_state["running"] = False


    add_balance(ctx.author.id, 100)
    await ctx.send(f"🏆 **{ctx.author.mention} zgarnął 100 Monet Reputacji! 💰**")



@bot.command(name="crime")
async def crime(ctx):
    user_id = ctx.author.id

    count = get_crime_count(user_id)

    if count >= 3:
        await ctx.send(f"🚔 {ctx.author.mention}, dziś już 3 przestępstwa. Policja mówi: idź spać.")
        return

    mission = random.choice(CRIME_LIST)

    add_crime_count(user_id)

    await ctx.send(
        f"🕵️ **Otrzymałeś zlecenie:**\n"
        f"👉 {mission}\n\n"
        f"⏳ Wynik za 1 minutę..."
    )

    await asyncio.sleep(60)
    try:
        success = random.choice([True, False])
        if success:
            add_balance(user_id, 100)
            await ctx.send("✅ **Misja zakończona... SUKCESEM**\n+100 Monet Reputacji 💰")
        else:
            add_balance(user_id, -100)
            await ctx.send("💀 **Misja zakończona... PORAŻKĄ**\n-100 Monet Reputacji")
    except discord.HTTPException as e:
        print(f"[crime] Nie można wysłać wyniku: {e}")

@bot.command()
async def rules(ctx):
    rules_text = """
📜 **REGULAMIN SERWERA (wersja: „nie rób dramy”)**

🧍‍♂️ 1️⃣ Szanuj innych. Tak, serio. Nie jesteś głównym bohaterem internetu.

🧠 2️⃣ Polityka i religia są zakazane. Ten serwer nie jest telewizją śniadaniową.

🚫 3️⃣ Spam i flood = szybka podróż poza serwer. Bez biletu powrotnego.

📢 4️⃣ Reklamy innych serwerów? Nie. To nie tablica ogłoszeń z 2008.

🎮 5️⃣ Cheatowanie w grach? Jeśli musisz oszukiwać, to może nie graj.

📌 6️⃣ Trzymaj się tematów kanałów. Chaos jest fajny… ale nie tutaj.

🛡️ 7️⃣ Administracja nie jest twoim wrogiem. Ale też nie twoim terapeutą.

☠️ 8️⃣ NSFW i rzeczy nielegalne? Nie. Internet już ma wystarczająco problemów.

🌍 9️⃣ Język: polski lub angielski. Inaczej wygląda to jak przypadkowe klikanie klawiatury.

🤖 🔟 I najważniejsze:
Nie rób rzeczy, przez które bot musi udawać, że jest rozczarowany ludzkością.
"""
    await ctx.send(rules_text)

#  PULE KOMENTARZY


INF_HIGH = [
    "INF przejął dowodzenie i nikt nie miał odwagi zapytać dlaczego.",
    "INF wygląda jakby reszta statystyk była tylko statystami w jego filmie.",
    "INF: \"ja tu jestem main character\", reszta: NPC confirmation.",
    "INF zdominował układ tak mocno, że balans gry wyszedł na papierosa i nie wrócił.",
    "INF nie jest statystyką. INF jest stanem zagrożenia.",
    "INF tak wysoki, że RANG i CAV zaczynają się zastanawiać nad zmianą zawodu.",
    "INF przejął kontrolę i nie odda jej nawet po patchu.",
    "INF wygląda jak exploit, ale dev udaje że to feature.",
    "INF robi za tank, DPS i moral support jednocześnie.",
    "INF powiedział \"ja tu prowadzę\" i system się zgodził.",
    "INF tak wysoki, że wykres przestał być legalny w 3 krajach.",
    "INF nie potrzebuje wsparcia. To wsparcie potrzebuje INF.",
    "INF wygrał zanim zaczęła się symulacja.",
    "INF to nie liczba. To ostrzeżenie.",
    "INF tak mocny, że logika poszła się przejść.",
]


INF_LOW = [
    "INF tak niski, że nawet kalkulator go ignoruje.",
    "INF w tej formie pełni funkcję dekoracyjną.",
    "INF istnieje bardziej jako sugestia niż realna statystyka.",
    "INF oddał rolę lidera i poszedł się schować.",
    "INF jest tu tylko dlatego, że system nie pozwala mu zniknąć.",
    "INF ma siłę oddziaływania jak mokra kartka papieru.",
    "INF nie prowadzi armii. INF obserwuje jak inni ją prowadzą.",
    "INF tak niski, że nawet RNG się nad nim lituje.",
    "INF jest w trybie oszczędzania energii.",
    "INF nie generuje presji, tylko zawód.",
    "INF został zredukowany do komentarza w patch notes.",
    "INF: \"ja tu jestem\"… nikt nie potwierdza.",
    "INF nie walczy, INF negocjuje porażkę.",
    "INF działa jak tutorial boss — szybko znika.",
    "INF to symbol pokory systemu.",
]


RANG_HIGH = [
    "RANG nie walczy z bliska, bo nie uznaje takich kontaktów.",
    "RANG gra w inną grę niż reszta.",
    "RANG ustawia się tak daleko, że serwer renderuje go w DLC.",
    "RANG nie potrzebuje ochrony, bo nikt nie dobiega.",
    "RANG zamienił mapę w symulator punktów obserwacyjnych.",
    "RANG nie atakuje. RANG kasuje decyzje wroga.",
    "RANG ma zasięg moralnie nielegalny.",
    "RANG stoi tak daleko, że INF zaczyna się denerwować.",
    "RANG nie celuje. RANG przewiduje przyszłość.",
    "RANG zamienia walkę w test reakcji CPU.",
    "RANG to argument przeciwko melee.",
    "RANG ma własny adres IP poza mapą.",
    "RANG nie jest wsparciem. RANG jest wyrokiem.",
    "RANG sprawia, że przeciwnik zastanawia się nad życiem.",
    "RANG: \"close combat? nie znam\".",
]


RANG_LOW = [
    "RANG jest blisko, bo nie miał wyboru.",
    "RANG próbował dystansu, ale dystans go nie chciał.",
    "RANG walczy jakby mapa była małym pokojem.",
    "RANG ma zasięg emocjonalny, nie bojowy.",
    "RANG istnieje w strefie ryzyka.",
    "RANG strzela i modli się o synchronizację.",
    "RANG to melee z ambicjami.",
    "RANG nie kontroluje dystansu. dystans kontroluje RANG.",
    "RANG: \"snajper\" — według CV.",
    "RANG trafia głównie w wspomnienia.",
    "RANG jest zawsze o krok za logiką walki.",
    "RANG działa jak broń jednorazowa, ale używana wielokrotnie.",
    "RANG ma kontakt z wrogiem częściej niż powinien.",
    "RANG nie supportuje dystansu. RANG go ignoruje.",
    "RANG: bliżej = szybciej kończy się nadzieja.",
]


CAV_HIGH = [
    "CAV wjeżdża zanim ktoś zdąży zrozumieć sytuację.",
    "CAV traktuje mapę jak parking.",
    "CAV nie flankuje. CAV demoluje kierunek.",
    "CAV to argument fizyczny, nie taktyczny.",
    "CAV ma subtelność młota pneumatycznego.",
    "CAV przyspiesza i problem przestaje istnieć.",
    "CAV ignoruje teren, bo teren i tak się dostosuje.",
    "CAV: \"strategia?\" — i tak jadę.",
    "CAV kończy dyskusje zanim się zaczną.",
    "CAV nie atakuje. CAV przejeżdża.",
    "CAV powoduje, że INF i RANG przestają się kłócić.",
    "CAV to decyzja \"tak\" napisana wielkimi literami.",
    "CAV nie potrzebuje planu. CAV jest planem.",
    "CAV zmienia walkę w katastrofę logistyczną.",
    "CAV wchodzi i system prosi o reset.",
]


CAV_LOW = [
    "CAV stoi, bo jeszcze nie dostał zgody na ruch.",
    "CAV ma ambicje, ale nie ma paliwa.",
    "CAV próbuje flankować, ale zapomniał jak się jeździ.",
    "CAV istnieje głównie w teorii.",
    "CAV to dekoracja pola bitwy.",
    "CAV nie przyspiesza. CAV rozważa przyspieszenie.",
    "CAV jest bardziej koncepcją niż jednostką.",
    "CAV boi się własnego cienia.",
    "CAV w trybie \"może później\".",
    "CAV próbuje być groźny, ale stoi w miejscu.",
    "CAV to backup plan, który nie został wdrożony.",
    "CAV: \"zaraz ruszam\" — od 3 tur.",
    "CAV nie flankuje, CAV czeka na inspirację.",
    "CAV to ruch w kolejce, który nigdy nie nadchodzi.",
    "CAV jest obecny, ale nie aktywny.",
]


@bot.command(name="gear")
async def gear(ctx, *args):


    # brak argumentów → instrukcja
    if len(args) == 0:
        await ctx.send(
            "🛡️ **GEAR ANALYZER 9000**\n\n"
            "Wrzuć swoje `%` w kolejności:\n"
            "`INF / RANG / CAV`\n\n"
            "Przykład:\n"
            "`?gear 130 50 20`\n\n"
            "⚠️ Liczy się **CAŁKOWITY ATK**.\n"
            "Czyli:\n"
            "- talenty mix\n"
            "- gear\n"
            "- bonusy\n"
            "- wszystko co naklikałeś o 3 nad ranem i już nie pamiętasz po co\n\n"
            "Masz 60 sekund zanim bot uzna cię za zaginionego w menu ekwipunku."
        )
        return


    # zła liczba argumentów lub nie-liczby → komunikat
    if len(args) != 3:
        await ctx.send("❌ Podaj dokładnie 3 wartości. Przykład: `?gear 130 50 20`")
        return


    try:
        a, b, c = map(float, args)
    except ValueError:
        await ctx.send("❌ Tylko liczby, nie słowa. Bot nie jest tłumaczem.")
        return


    # walidacja ujemnych
    if a < 0 or b < 0 or c < 0:
        await ctx.send("❌ Wartości nie mogą być ujemne. Nawet twój gear ma swoje granice.")
        return


    input_vals = [a, b, c]
    total_attack = sum(input_vals)


    if total_attack == 0:
        await ctx.send(
            "📊 **Wynik analizy**\n\n"
            "Formacja: `0 / 0 / 0`\n"
            "Łączny atak: `0%`\n\n"
            "🛡️ INF nie istnieje. INF jest ideą.\n"
            "🏹 RANG nie trafia, bo nie ma w co.\n"
            "🐎 CAV stoi i zastanawia się nad sensem bytu."
        )
        return


    # ── algorytm skalowania──
    exact = [(v / total_attack) * 20.0 for v in input_vals]
    result = [math.floor(x) for x in exact]


    used = sum(result)
    remaining = int(20 - used)


    fractions = [(exact[i] - result[i], i) for i in range(3)]
    fractions.sort(reverse=True, key=lambda x: x[0])


    for i in range(remaining):
        result[fractions[i][1]] += 1


    inf_val  = result[0]
    rang_val = result[1]
    cav_val  = result[2]


    # ── losowanie komentarzy ──
    comment_inf  = random.choice(INF_HIGH  if inf_val  > 5 else INF_LOW)
    comment_rang = random.choice(RANG_HIGH if rang_val > 5 else RANG_LOW)
    comment_cav  = random.choice(CAV_HIGH  if cav_val  > 5 else CAV_LOW)


    # ── odpowiedź ──
    await ctx.send(
        f"📊 **Wynik analizy**\n\n"
        f"Formacja: `{inf_val} / {rang_val} / {cav_val}`\n"
        f"Łączny atak: `{int(total_attack)}%`\n\n"
        f"🛡️ {comment_inf}\n"
        f"🏹 {comment_rang}\n"
        f"🐎 {comment_cav}"
    )


@bot.command()
async def help(ctx):
    help_text = """
🤖 **LISTA KOMEND BOTA (wersja: „ten serwer żyje własnym życiem”)**

---

🛡️ **MODERACJA**
🚨 `?warn @user [powód]` – ostrzeżenie  
🔇 `?mute @user [powód]` – wyciszenie  
🔊 `?unmute @user` – cofnięcie mute  
👢 `?kick @user [powód]` – wyrzucenie z serwera  

---

ℹ️ **INFORMACYJNE**
📢 `?important @user/rola [wiadomość]` – DM ważna wiadomość  
📜 `?rules` – regulamin (bot ma już dość ludzi)  
🛡️ `?shield @user` – brak tarczy (DM)  
📊 `?gear` – test sprzętu pod formacje
📨 `?spamshield @user [ilość]` – spam DM (max 10)  
📊 `?kontrlist` – lista konter (tworzona przez LW)
🖨️ `?print [wiadomość]` – bot powtarza  

---

🎮 **OBRAZKI I PRZEPOWIEDNIE**
❓ `?8ball` / `?8ballfun` – odpowiedzi na pytania TAK/NIE 
🐱 `?cat` – kotek  
🐶 `?dog` – piesek  
🖼️ `?specjal` – losowy obrazek tematyczny

---

💰 **EKONOMIA I SYSTEM ZABAWY**
💰 `?saldo` – Pokazuje Twoje monety Reputacji ♾️  
💰 `?rank` – Pokazuje dostępne ligi ♾️  
🎁 `?daily` – 💰 +10  ⏳ 1x/dzień  
🕵️ `?crime` – ryzyko 💰 +100 / 💸 -100 ⏳ 3x/dzień  
⚡ `?reflex` – event 💰 +100 (kto pierwszy) ⏳ 1x/dzień  
⚡ `?caim reflex` – kto pierwszy wbije po haśle TERAZ 💰 +100  
🎰 `?casino` – hazard 💸 +100 💰 +500 / 💸 -10 ⏳ 2x/dzień  

🎲 `?roll` – 💰 +1000 / 💸 -50 ⏳ 4x/dzień  
✊ `?rps` – 💰 +30 / 0 / 💸 -10 ⏳ 5x/dzień  
🪙 `?coinflip` – 💰 +30 / 💸 -30 ⏳ 2x/dzień  
🃏 `?3cards` – 💸 -30 /💰 +100-250 / 💸 -40-90 ⏳ 3x/dzień  
🎡 `?roulette` – 💸 -40 /💰 +80 /💰 +<10 000 / 💸 -40-90 ⏳ 4x/dzień  
---

📌 **PING**
🏓 `?ping` – sprawdza czy bot żyje ♾️  

"""

    await ctx.send(help_text)

@bot.command()
async def kontrlist(ctx):
    kontr = [
        "📜 **Kontry standardowe**:",
        "• przeciwko 884 użyj 848",
        "• przeciwko 488 użyj 884",
        "• przeciwko 569 użyj 848", 
        "• przeciwko 848 użyj 659",
        "• przeciwko 488 użyj 659",
        "📜 **Kontry specjalne**:",
        "• przeciwko 488 użyj 13 5 2", 
        "• przeciwko 569 użyj 13 5 2",
        "• przeciwko 659 użyj 848",
        "• przeciwko 848 użyj 848",
        "• przeciwko 884 użyj 13 5 2",
        "• przeciwko 677 użyj 13 5 2", 
        "• przeciwko 767 użyj 13 5 2",
        "• przeciwko 776 użyj 11 7 2",
        "• przeciwko 13 5 2 użyj 13 5 2",
        "• przeciwko 5 11 4 użyj 11 7 2",
        "• przeciwko 11 7 2 użyj 13 5 2"
    ]
    embed = discord.Embed(
        title="📜 Lista konter",
        description="\n".join(kontr),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command()
async def rank(ctx):
    text = """
🏆 **SYSTEM LIG MONET REPUTACJI**

Im więcej Monet Reputacji zdobywasz, tym wyższą ligę osiągasz.
Bot codziennie sprawdza saldo i automatycznie przyznaje odpowiednią rangę 🪙

🎨 Wyższe ligi:
• dają kolor nicku
• zwiększają widoczność na serwerze
• pokazują status społeczny
• sprawiają, że ludzie zaczynają traktować cię podejrzanie poważnie

⚔️ Rywalizuj ze znajomymi i wspinaj się po drabinie ekonomicznego chaosu.

---

🪙 **Liga I – Nowicjusze Systemu**
💰 0 – 5 000
„Serwer nadal nie wie, czy masz ambicje czy tylko Wi-Fi.”

---

🪙 **Liga II – Rekruci Obiecanek**
💰 5 001 – 15 000
„System cię rozpoznaje, ale nadal ci nie ufa.”

---

🪙 **Liga III – Zbieracze Okruszków**
💰 15 001 – 30 000
„Masz już coś. Nadal jednak żywisz się resztkami ekonomii.”

---

🪙 **Liga IV – Lokalni Gracze**
💰 30 001 – 60 000
„Masz pozycję. Czy imponującą? Dyskusyjne.”

---

🪙 **Liga V – Operujący Kapitałem**
💰 60 001 – 100 000
„Brzmisz jak ktoś kompetentny. To jeszcze niczego nie dowodzi.”

---

🪙 **Liga VI – Architekci Ekonomii**
💰 100 001 – 150 000
„Ludzie zaczynają wierzyć, że masz plan.”

---

🪙 **Liga VII – Elita Systemu**
💰 150 001 – 200 000
„System działa bardziej dla ciebie niż przeciwko tobie.”

---

🪙 **Liga VIII – Legendy Bilansu**
💰 200 000+
„Nie grasz już w grę. Ty jesteś błędem ekonomii.”

---

🤖 Awans lub degradacja odbywa się automatycznie raz dziennie.
💀 Tak, możesz spaść z ligi. System pamięta wszystko.
"""
    
    await ctx.send(text)

@bot.command()
async def specjal(ctx):
    await send_christmas_embed(ctx.channel)


@bot.command(name="roulette")
async def roulette(ctx):
    user_id = ctx.author.id


    # 🔒 LIMIT 4 DZIENNIE
    count = get_roulette_count(user_id)
    if count >= 4:
        await ctx.send(
            f"⏳ {ctx.author.mention}, wykorzystałeś już **4 ruletki** dziś. "
            f"Wróć jutro i znów oddaj swoje monety kołu."
        )
        return


    # 💰 SPRAWDZENIE SALDA
    balance = get_balance(user_id)
    free_spin = balance < 0


    jackpot = get_jackpot_pool()


    if free_spin:
        cost_info = "🆓 Twoje saldo jest ujemne — ten spin jest **darmowy** (do puli nic nie trafia)."
    else:
        cost_info = f"💰 Koszt gry: **{ROULETTE_COST} monet reputacji**."


    await ctx.send(
        f"🎡 {ctx.author.mention}, **ruletka uruchomiona!**\n\n"
        f"{cost_info}\n"
        f"💎 Aktualna pula jackpot: **{jackpot}**\n\n"
        f"Wpisz: `?roulette [zakład]`\n"
        f"Dostępne zakłady: `czerwone`, `czarne`, `zielone`, `parzyste`, `nieparzyste` lub **liczba 0–36**\n\n"
        f"⏳ Masz **1 minutę**."
    )


    
    def check(msg):
        return (
            msg.author == ctx.author
            and msg.channel == ctx.channel
            and not msg.embeds
        )

active_games.add(user_id)
    try:
        response = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        await ctx.send(
            f"⏳ {ctx.author.mention}, ruletka się zamknęła. "
            f"Koło nie czeka na niezdecydowanych."
        )
        return
    active_games.add(user_id)



raw = response.content.strip().lower()


    # Wymaga prefiksu ?
    if not raw.startswith("?"):
        await ctx.send(
            f"❌ Zakład musi zaczynać się od `?`. Np. `?czerwone`, `?17`, `?parzyste`."
        )
        return


    raw_bet = raw[1:].strip()  # odcinamy ?


    # Obsługa "?roulette [zakład]" zamiast samego zakładu
    if raw_bet.startswith("roulette "):
        raw_bet = raw_bet[len("roulette "):].strip()


    is_number = raw_bet.isdigit() and 0 <= int(raw_bet) <= 36


    if raw_bet not in ALLOWED_BETS and not is_number:
        await ctx.send(
            f"❌ **'?{raw_bet}'** nie jest poprawnym zakładem. "
            f"Ruletka nie obsługuje improwizacji."
        )
        return


    # ✅ WALIDACJA OK — dopiero teraz pobieramy opłatę i liczymy spin
    if not free_spin:
        add_balance(user_id, -ROULETTE_COST)
    set_roulette_count(user_id, count + 1)


    # 🎡 ANIMACJA
    steps = random.randint(5, 15)
    delays = []
    d = 0.8
    for i in range(steps):
        delays.append(d)
        d = round(d + (0.6 / steps), 2)


    all_numbers = list(range(0, 37))


    spin_msg = await ctx.send("🎡 **Kręcę ruletką...**\n\n⬛ ...")


    final = random.choice(all_numbers)
    final_color = get_roulette_color(final)


    for i, delay in enumerate(delays):
        fake_n = random.choice(all_numbers)
        fake_color = get_roulette_color(fake_n)
        suffix = " ⏳ ..." if i == len(delays) - 1 else ""
        await spin_msg.edit(
            content=f"🎡 **Kręcę ruletką...**\n\n{fake_color} {fake_n}{suffix}"
        )
        await asyncio.sleep(delay)


    # 🏆 WYNIK
    win = False
    jackpot_win = (final == 0)


    if raw_bet == "czerwone" and final_color == "🟥":
        win = True
    elif raw_bet == "czarne" and final_color == "⬛":
        win = True
    elif raw_bet == "zielone" and jackpot_win:
        win = True  # zielone = gracze obstawi 0 = jackpot i tak
    elif raw_bet == "parzyste" and final != 0 and final % 2 == 0:
        win = True
    elif raw_bet == "nieparzyste" and final % 2 == 1:
        win = True
    elif is_number and int(raw_bet) == final:
        win = True
        if final == 0:
            jackpot_win = True  # obstawi konkretnie 0


    # Jackpot zawsze wygrywa pulę, niezależnie od zakładu
    if jackpot_win:
        payout = jackpot
        add_balance(user_id, payout)
        set_jackpot_pool(JACKPOT_RESET)
        comment = random.choice(JACKPOT_RESPONSES)
        result_line = (
            f"💥 **JACKPOT!!!** 💥\n"
            f"💰 +**{payout}** monet reputacji\n"
            f"💎 Pula zresetowana do {JACKPOT_RESET}"
        )
    elif win:
        reward = ROULETTE_COST * 2
        add_balance(user_id, reward)
        if not free_spin:
            set_jackpot_pool(jackpot + 20)
        comment = random.choice(WIN_RESPONSES)
        result_line = (
            f"✨ **WYGRANA!**\n"
            f"💰 +**{reward}** monet reputacji"
        )
    else:
        if not free_spin:
            set_jackpot_pool(jackpot + 10)
        comment = random.choice(FAIL_RESPONSES)
        result_line = "💀 **PRZEGRANA.**"


    new_jackpot = get_jackpot_pool()


    await spin_msg.edit(
        content=(
            f"🎡 Wypadło...\n\n"
            f"{final_color} **{final}**\n\n"
            f"{result_line}\n\n"
            f"💎 Aktualna pula wynosi: **{new_jackpot}**\n"
            f"_{comment}_"
        )
    )


@bot.command(name="3cards")
async def three_cards(ctx):
    user_id = ctx.author.id


    # 🔒 LIMIT DZIENNY
    count = get_cards_count(user_id)
    if count >= CARDS_LIMIT:
        await ctx.send(
            f"⏳ {ctx.author.mention}, widziałeś już dziś **{CARDS_LIMIT} zestawy kart**. "
            f"Karty nie chcą cię więcej widzieć. Wzajemnie."
        )
        return


    # 💰 SPRAWDZENIE SALDA
    balance = get_balance(user_id)
    free_spin = balance < 0


    if not free_spin and balance < CARDS_ENTRY_FEE:
        await ctx.send(
            f"💸 {ctx.author.mention}, nie masz **{CARDS_ENTRY_FEE} monet** na wejście. "
            f"Masz: **{balance}**. Karty nie grają z biedakami. Chyba że jesteś w minusie — to grasz za free."
        )
        return


    if free_spin:
        cost_info = "🆓 Saldo ujemne — ten zestaw jest **darmowy**."
    else:
        cost_info = f"💰 Gra kosztuje **{CARDS_ENTRY_FEE} Monet**."


    await ctx.send(
        f"🃏 {ctx.author.mention}, {cost_info}\n\n"
        "Karty leżą przed Tobą.\n"
        "Każda wygląda tak samo.\n"
        "Każda coś ukrywa.\n\n"
        "` [ 1 ] `   ` [ 2 ] `   ` [ 3 ] `\n"
        "     🃏            🃏            🃏\n\n"
        "Wybierz: **?1 / ?2 / ?3**\n"
        "⏳ Masz minutę zanim znikną bez śladu..."
    )


    def check(msg):
        return (
            msg.author == ctx.author
            and msg.channel == ctx.channel
            and msg.content.strip() in ["?1", "?2", "?3"]
        )


active_games.add(user_id)
    try:
        choice_msg = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        active_games.discard(user_id)
        await ctx.send(
            f"⏳ {ctx.author.mention}, karty obróciły się w proch. "
            f"Monety zostają — okazja nie."
        )
        return
    active_games.discard(user_id)



    # ✅ WALIDACJA OK — dopiero teraz pobieramy opłatę
    if not free_spin:
        add_balance(user_id, -CARDS_ENTRY_FEE)
    set_cards_count(user_id, count + 1)


    # 🎴 LOSOWANIE KART — 1 dobra, 2 złe, z dużych pul
    good = random.choice(GOOD_CARDS)
    bad1 = random.choice(BAD_CARDS)
    bad2 = random.choice([c for c in BAD_CARDS if c is not bad1])


    good_val = random.randint(*good["val_range"])
    bad1_val = random.randint(*bad1["val_range"])
    bad2_val = random.randint(*bad2["val_range"])


    cards = [
        {**good, "val": good_val},
        {**bad1, "val": bad1_val},
        {**bad2, "val": bad2_val},
    ]
    random.shuffle(cards)


    chosen_index = int(choice_msg.content.strip()[1]) - 1  # "?2" → 1
    selected = cards[chosen_index]


    add_balance(user_id, selected["val"])


    visual = ["🃏", "🃏", "🃏"]
    visual[chosen_index] = selected["emoji"]


    change_text = f"+{selected['val']}" if selected["val"] > 0 else str(selected["val"])


    await ctx.send(
        f"Odsłaniasz kartę nr **{chosen_index + 1}**...\n\n"
        f"` [ 1 ] `   ` [ 2 ] `   ` [ 3 ] `\n"
        f"   {visual[0]}          {visual[1]}          {visual[2]}\n\n"
        f"🃏 **\"{selected['name']}\"**\n"
        f"💰 Zmiana balansu: **{change_text} Monet**\n"
        f"🔮 *{selected['desc']}*\n\n"
        f"*Reszta kart znika w absolutnej ciszy.*"
    )

    
bot.run(TOKEN)

















































