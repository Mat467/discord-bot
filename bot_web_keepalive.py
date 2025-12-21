import os
import discord
import random
import io
import asyncio
import aiohttp
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")  # wstaw swój key do env na Renderze
session = None  # będzie utworzona później

# --- konfiguracja z ENV ---
TOKEN = os.environ.get("DISCORD_TOKEN")
MODERATORS = [int(x) for x in os.environ.get("MODERATORS", "").split(",") if x.strip()]


if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")


intents = discord.Intents.default()
intents.members = True
intents.message_content = True


bot = commands.Bot(command_prefix='?', intents=intents, help_command=None)
# ------------------------------
# Podmiana ctx.send globalnie, aby wszystkie wiadomości były embedami z czerwoną ramką
# ------------------------------
original_send = commands.Context.send  # zachowujemy oryginalną funkcję


async def new_send(ctx, *args, **kwargs):
    # Jeśli wysyłany jest embed, ustawiamy kolor czerwony
    if "embed" in kwargs and kwargs["embed"]:
        kwargs["embed"].color = discord.Color.red()
        return await original_send(ctx, *args, **kwargs)


    # Jeśli wysyłany jest zwykły tekst, pakujemy go do embedu z czerwoną ramką
    if args:
        text = args[0]
        embed = discord.Embed(description=text, color=discord.Color.red())
        return await original_send(ctx, embed=embed, **kwargs)


    # Jeżeli nie ma nic do wysłania, wywołujemy oryginalne ctx.send
    return await original_send(ctx, *args, **kwargs)


# Podmieniamy globalnie ctx.send
commands.Context.send = new_send

app = Flask("")


@app.route("/")
def home():
    return "Bot alive"


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# uruchom serwer HTTP w osobnym wątku (Render poda PORT automatycznie)
Thread(target=run_flask).start()

CHRISTMAS_THEMES = {
    "🎄 Choinka": {"query": "christmas,tree", "color": 0x2ECC71, "texts": ["🎄 Świąteczna propaganda obowiązkowa","🎄 Choinka stoi. Regulamin też.","🎄 Ten moment, gdy drzewko ma więcej ozdób niż role","🎄 Administracja potwierdza: to jest choinka"]},
    "🎅 Mikołaj": {"query": "santa,claus,christmas", "color": 0xE74C3C, "texts": ["🎅 Ho ho ho. Logi były sprawdzane.","🎅 Mikołaj widzi więcej niż moderator","🎅 Prezentów brak, ale klimat jest","🎅 Regulamin grzecznych obowiązuje cały rok"]},
    "🦌 Renifery": {"query": "reindeer,christmas,winter", "color": 0xA04000, "texts": ["🦌 Renifer na służbie. Zaprzęg w gotowości.","🦌 Rudolf twierdzi, że to nie jego wina","🦌 Bez reniferów nie ma logistyki świąt","🦌 Ten gość ciągnie cały projekt"]},
    "❄️ Zima": {"query": "winter,snow", "color": 0x5DADE2, "texts": ["❄️ Zima przyszła. Produktywność wyszła.","❄️ Śnieg pada, serwer nadal żyje","❄️ Idealna pogoda na nieodpisywanie","❄️ Mróz na zewnątrz, ciepło na czacie"]},
    "🎁 Prezenty": {"query": "christmas,gifts", "color": 0xF4D03F, "texts": ["🎁 Najlepszy prezent to brak pingów","🎁 Administracja nic nie obiecuje","🎁 Opakowanie ładniejsze niż zawartość","🎁 Tak, to też się liczy"]},
    "☕ Klimat": {"query": "christmas,cozy", "color": 0xAF7AC5, "texts": ["☕ Tryb koc + herbata aktywny","☕ Oficjalnie: nic nie musisz","☕ To nie lenistwo, to święta","☕ Discord, cisza i zero planów"]},
    "🏠 Dom": {"query": "christmas,home", "color": 0xDC7633, "texts": ["🏠 Domowy tryb serwera","🏠 Bez pośpiechu, bez dram","🏠 Nawet bot zwalnia tempo","🏠 Tu się odpoczywa"]},
    "🔥 Ogień": {"query": "fireplace,winter", "color": 0xCB4335, "texts": ["🔥 Idealne tło do ignorowania obowiązków","🔥 Ogień trzaska, czat żyje","🔥 Legalne źródło ciepła","🔥 Klimat zatwierdzony"]},
    "🌌 Noc": {"query": "christmas,night", "color": 0x1F618D, "texts": ["🌌 Nocna wersja świąt","🌌 Cisza, spokój, Discord","🌌 Idealna pora na memy","🌌 Bot nadal czuwa. Niestety."]}
}
async def send_christmas_embed(ctx_or_channel, attempt=1):
    title, data = random.choice(list(CHRISTMAS_THEMES.items()))
    text = random.choice(data["texts"])

    query = data["query"].replace(",", "+").replace(" ", "+") + "+christmas"
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&page={random.randint(1,10)}"
    headers = {"Authorization": PEXELS_API_KEY}

    embed = discord.Embed(title=title, description=text, color=data["color"])

    try:
        async with session.get(url, headers=headers) as resp:
            print("PEXELS STATUS:", resp.status)

            if resp.status != 200:
                body = await resp.text()
                print("PEXELS BODY:", body)

                if attempt < 3:
                    print(f"PEXELS: retry za 10 minut (próba {attempt + 1})")
                    asyncio.create_task(retry_christmas_embed(ctx_or_channel, attempt + 1))
                else:
                    error_embed = discord.Embed(
                        title="❌ Błąd Pexels",
                        description=f"Błąd {resp.status}. Nie udało się wysłać obrazka! Ale moja administracja już pilnie pracuje nad rozwiązaniem tego problemu...",
                        color=0xE74C3C
                    )
                    await ctx_or_channel.send(embed=error_embed)
                return

            json_data = await resp.json()

            if not json_data.get("photos"):
                print("PEXELS: brak zdjęć dla query:", query)
                if attempt < 3:
                    print(f"PEXELS: retry za 10 minut (próba {attempt + 1})")
                    asyncio.create_task(retry_christmas_embed(ctx_or_channel, attempt + 1))
                else:
                    error_embed = discord.Embed(
                        title="❌ Błąd Pexels",
                        description=f"Brak zdjęć dla zapytania. Nie udało się wysłać obrazka po 3 próbach!",
                        color=0xE74C3C
                    )
                    await ctx_or_channel.send(embed=error_embed)
                return

            photo = random.choice(json_data["photos"])
            image_url = photo["src"]["large2x"]

            async with session.get(image_url) as img_resp:
                if img_resp.status != 200:
                    print("IMAGE STATUS:", img_resp.status)
                    if attempt < 3:
                        print(f"PEXELS: retry za 10 minut (próba {attempt + 1})")
                        asyncio.create_task(retry_christmas_embed(ctx_or_channel, attempt + 1))
                    else:
                        error_embed = discord.Embed(
                            title="❌ Błąd pobierania obrazka",
                            description=f"Błąd {img_resp.status}. Nie udało się wysłać obrazka po 3 próbach!",
                            color=0xE74C3C
                        )
                        await ctx_or_channel.send(embed=error_embed)
                    return

                image_data = await img_resp.read()
                file = discord.File(
                    fp=io.BytesIO(image_data),
                    filename="swieta.jpg"
                )
                embed.set_image(url="attachment://swieta.jpg")
                await ctx_or_channel.send(embed=embed, file=file)
                return  # sukces

    except Exception as e:
        print("CHRISTMAS EMBED ERROR:", e)
        if attempt < 3:
            print(f"PEXELS: retry za 10 minut (próba {attempt + 1})")
            asyncio.create_task(retry_christmas_embed(ctx_or_channel, attempt + 1))
        else:
            error_embed = discord.Embed(
                title="❌ Błąd Pexels",
                description=f"Nie udało się wysłać obrazka po 3 próbach! Błąd: {e}",
                color=0xE74C3C
            )
            await ctx_or_channel.send(embed=error_embed)
        return

CHANNEL_ID = 1437924798645928106  # <-- wstaw swoje ID kanału

# --- Loop świąteczny ---
@tasks.loop(hours=8)
async def christmas_loop():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await send_christmas_embed(channel)  # ZMIANA: użycie nowej funkcji
    else:
        print(f"Nie znalazłem kanału o ID {CHANNEL_ID}")
            
@bot.event
async def on_ready():
    global session  # <-- dodaj to, żeby modyfikować globalną zmienną
    print(f'Bot logged in as {bot.user}')
    
    if session is None:  # <-- dodaj to – tworzy sesję tylko raz, gdy potrzeba
        session = aiohttp.ClientSession()
    
    if not christmas_loop.is_running():
        christmas_loop.start()
		
# 🟢 AUTO-POWITANIE
@bot.event
async def on_member_join(member):
    # znajdź kanał powitań po nazwie
    channel = discord.utils.get(member.guild.text_channels, name="powitania")
    if channel:
        await channel.send(f"🎉 Witamy nowego członka: {member.mention}! Dajcie mu serduszko ❤️")

@bot.event
async def on_message(message):
    # ignorujemy własne wiadomości
    if message.author == bot.user:
        return
    
    # jeśli ktoś pisze PRIV do bota
    if isinstance(message.channel, discord.DMChannel):
        await message.channel.send("Cześć! Ja reaguję tylko na komendy zaczynające się od `?`. Spróbuj np. `?ping`")
        return
    
    # jeśli to normalna wiadomość na serwerze – sprawdzamy komendy
    await bot.process_commands(message)

# -------- twoje komendy (przykład) --------
# wklej tu dokładnie swoje funkcje warn, important, kick, mute, shield, ping
# poniżej skrócona wersja — wklej pełne definicje jakie masz lokalnie

@bot.command()
async def warn(ctx, member: discord.Member, *, reason="Brak powodu"):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie masz uprawnień do tej komendy!")
        return
    await ctx.send(f"{member.mention} otrzymał ostrzeżenie: {reason}")
    try:
        await member.send(f"Otrzymałeś ostrzeżenie na serwerze {ctx.guild.name}: {reason}")
    except:
        await ctx.send("Nie mogę wysłać DM do tego użytkownika.")


@bot.command()
async def mute(ctx, member: discord.Member, *, reason="Brak powodu"):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie masz uprawnień do tej komendy!")
        return
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Rola 'Muted' nie istnieje.")
        return
    await member.add_roles(muted_role)
    await ctx.send(f"🔇 {member.name} został wyciszony. Powód: {reason}")
	
@bot.command()
async def spamshield(ctx, member: discord.Member, times: int = 5):
    """Spamuje DM o tarczy do wskazanego gracza (domyślnie 5 razy, max 10)."""
    
    # ograniczenie, żeby nie przesadzić
    times = max(1, min(times, 10))  
    
    sent = 0
    for i in range(times):
        try:
            await member.send("🛡️ Użyj tarczy! Wróg nadciąga!")
            sent += 1
        except:
            await ctx.send(f"❌ Nie mogę wysłać wiadomości do {member.name}.")
            return
    
    await ctx.send(f"✅ Wysłałem {sent} ostrzeżeń do {member.mention} na priv.")

@bot.command()
async def unmute(ctx, member: discord.Member):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie masz uprawnień do tej komendy!")
        return
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Rola 'Muted' nie istnieje.")
        return
    try:
        await member.remove_roles(muted_role)
        await ctx.send(f" {member.name} został odciszony.")
    except:
        await ctx.send("Nie mogę odciszyć tego użytkownika.")

# ?kick - wyrzucenie (tylko moderatorzy)
@bot.command()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie wolno używać tego polecenia!")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member.name} został wyrzucony. ({reason})")
    except:
        await ctx.send("Nie mogę wyrzucić tego użytkownika.")

# --- Ważne wiadomości ---


@bot.command()
async def important(ctx, *, message):
    if not ctx.message.mentions and not ctx.message.role_mentions and "@everyone" not in ctx.message.content:
        await ctx.send("Musisz oznaczyć gracza, rolę lub @everyone.")
        return


    notified = []


    # oznaczeni użytkownicy
    for member in ctx.message.mentions:
        try:
            await member.send(f"🔔 Masz nową ważną wiadomość: {message}")
            notified.append(member.name)
        except:
            await ctx.send(f"Nie mogę wysłać wiadomości do {member.name}.")


    # oznaczone role
    for role in ctx.message.role_mentions:
        for member in role.members:
            try:
                await member.send(f"🔔 Masz nową ważną wiadomość dla roli {role.name}: {message}")
                notified.append(member.name)
            except:
                await ctx.send(f"Nie mogę wysłać wiadomości do {member.name}.")


    # @everyone
    if "@everyone" in ctx.message.content:
        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                await member.send(f"🔔 Masz nową ważną wiadomość: {message}")
                notified.append(member.name)
            except:
                pass  # wielu userów może mieć zablokowane DM


    if notified:
        await ctx.send(f"Powiadomiłem {len(notified)} graczy jako ważne.")

# ?shield - dostępne dla wszystkich
@bot.command()
async def shield(ctx, member: discord.Member):
    try:
        await ctx.send(f"{member.mention} gracz został poinformowany o braku tarczy")
        await member.send("Użyj tarczy! Wróg już nadciąga!")
    except:
        await ctx.send("Nie mogę wysłać PW do tego użytkownika.")

# --- Zabawa ---


@bot.command()
async def roll(ctx, sides: int = 100):
    result = random.randint(1, sides)
    await ctx.send(f"🎲 {ctx.author.name} rzucił kostką ({sides}) i wypadło **{result}**")


@bot.command()
async def coinflip(ctx):
    result = random.choice(["orzeł ", "reszka "])
    await ctx.send(f"{ctx.author.name} rzucił monetą: **{result}**")


@bot.command(name="8ball")
async def eight_ball(ctx, *, question: str):
    responses = [
        "Tak!", "Nie.", "Może...", "Raczej tak.", "Raczej nie.",
        "Zdecydowanie!", "Lepiej nie pytaj.", "Ciężko powiedzieć."
    ]
    answer = random.choice(responses)
    await ctx.send(f"Pytanie: {question}\nOdpowiedź: **{answer}**")

@bot.command()
async def eightballfun(ctx, *, question: str):
    responses = [
        "😂 Hahaha, dobre pytanie!",
        "🔮 Zapytaj jutro, dziś nie wróżę.",
        "🍕 Może tak, może nie. A może pizza?",
        "🙃 Czemu pytasz mnie, skoro masz Google?",
        "💔 Nie chcę łamać Ci serca, ale… nope.",
        "😏 Zastanów się jeszcze raz i udawaj, że nigdy nie pytałeś.",
        "🤡 To najgłupsze pytanie jakie dziś usłyszałem.",
        "🔥 Jasne! A teraz wracaj do roboty.",
        "🌚 Powiedzmy, że odpowiedź brzmi: meh.",
        "🦄 42. Zawsze 42."
    ]
    await ctx.send(f"**{ctx.author.display_name} pyta:** {question}\n🎱 {random.choice(responses)}")


# ✊✋✌️ RPS – Kamień papier nożyce
@bot.command()
async def rps(ctx, choice: str):
    choices = ["kamień", "papier", "nożyce"]
    bot_choice = random.choice(choices)
    choice = choice.lower()

    if choice not in choices:
        await ctx.send("Użyj: `?rps kamień`, `?rps papier` albo `?rps nożyce`.")
        return

    # logika gry
    if choice == bot_choice:
        result = "Remis!"
    elif (choice == "kamień" and bot_choice == "nożyce") or \
         (choice == "papier" and bot_choice == "kamień") or \
         (choice == "nożyce" and bot_choice == "papier"):
        result = "Wygrałeś! 🎉"
    else:
        result = "Przegrałeś! 😢"

    await ctx.send(f"Ty: **{choice}** | Bot: **{bot_choice}** → {result}")

@bot.command()
async def cat(ctx):
    url = "https://api.thecatapi.com/v1/images/search"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                image_url = data[0]["url"]  # bezpośredni link do jpg/png
                embed = discord.Embed(title="🐱 Twój losowy kotek!", color=0xFF9900)
                embed.set_image(url=image_url)
                await ctx.send(embed=embed)
            else:
                await ctx.send("😿 Nie udało się znaleźć kota, spróbuj ponownie!")
				
# --- Pomoc i zasady ---

@bot.command()
async def print(ctx, *, text: str):
    # usuń wiadomość użytkownika (opcjonalnie)
    try:
        await ctx.message.delete()
    except:
        pass  # jeśli bot nie ma uprawnień, po prostu pomija

    # wyślij treść
    await ctx.send(text)
	
@bot.command()
async def help(ctx):
    help_text = """
**Lista komend bota**


Moderacja:
- `?warn @user [powód]` – wysyła ostrzeżenie
- `?mute @user [powód]` – wycisza użytkownika
- `?unmute @user` – cofa wyciszenie
- `?kick @user` – usuwa z serwera

 Informacyjne:
- `?important @user [wiadomość]` – wysyła ważną wiadomość
- `?rules` – pokazuje zasady serwera
- `?shield @user` – informuje o braku tarczy
- `?spamshield @user [ilość max 10]` – wysyła spam tarczy do użytkownika 
- `?kontrlist` – wysyła listę konter 
- `?print [wiadomość]` – wysyła wiadomość o podanej treści 

Zabawa:
- `?roll [sides]` – rzut kostką (domyślnie 1–100)
- `?coinflip` – rzut monetą
- `?8ball [pytanie]` – magiczna kula
- `?8ballfun [pytanie]` – rozbudowana magiczna kula
- `?cat` - wysyła losowego kotka
- `?rps [wybór]` – gra w Kamień papier nożyce

 Narzędzia:
- `?ping` – sprawdza czy bot działa
"""
    await ctx.send(help_text)


@bot.command()
async def rules(ctx):
    rules_text = """
**Zasady serwera:**


1️ Szanuj innych – zero obrażania i wyzwisk.  
2️ Brak polityki i religii – to nie miejsce na takie dyskusje.  
3️ Nie spamuj i nie flooduj wiadomości.  
4️ Zakaz reklamowania innych serwerów/stron.  
5️ Nie używaj cheatów ani exploitów w grach.  
6️ Trzymaj się tematów kanałów.  
7️ Słuchaj administracji i moderatorów.  
8️ Zakaz udostępniania treści NSFW i nielegalnych.  
9️ Używaj języka polskiego lub angielskiego (jeśli ustalono).  
10 Pamiętaj – baw się dobrze i wspieraj klimat serwera!
"""
    await ctx.send(rules_text)

@bot.command()
async def kontrlist(ctx):
    kontr = [
    	"Kontry standardowe",
	"przeciwko 884 użyj 848",
        "przeciwko 488 użyj 884",
        "przeciwko 569 użyj 848", 
        "przeciwko 848 użyj 659",
        "przeciwko 488 użyj 659",
	"Kontry specjalne",
        "przeciwko 488 użyj 13 5 2", 
        "przeciwko 569 użyj 13 5 2",
        "przeciwko 659 użyj 848",
	"przeciwko 848 użyj 848",
        "przeciwko 884 użyj 13 5 2",
        "przeciwko 677 użyj 13 5 2", 
        "przeciwko 767 użyj 13 5 2",
        "przeciwko 776 użyj 11 7 2",
	"przeciwko 13 5 2 użyj 13 5 2",
        "przeciwko 5 11 4 użyj 11 7 2",
        "przeciwko 11 7 2 użyj 13 5 2", 
    ]

    embed = discord.Embed(
        title="📜 Lista konter",
        description="\n".join(kontr),
        color=discord.Color.blue()  # możesz zmienić np. na .green(), .red()
    )


    await ctx.send(embed=embed)
    
# --- Ping ---


@bot.command()
async def ping(ctx):
    await ctx.send(" Pong! Bot działa.")
	
@bot.command()
async def swieta(ctx):
    await send_christmas_embed(ctx)  # ZMIANA: użycie nowej funkcji
# start bota (discord.py run blokuje wątek główny — Flask już działa w osobnym wątku)
@bot.event
async def on_disconnect():
    global session  # <-- dodaj to
    if session and not session.closed:  # <-- dodaj sprawdzenie, żeby nie crashować
        await session.close()
		
# --- retry ---
async def retry_christmas_embed(ctx_or_channel, attempt):
    print(f"PEXELS: retry za 10 minut (próba {attempt})")
    await asyncio.sleep(600)  # 10 minut
    await send_christmas_embed(ctx_or_channel, attempt)


bot.run(TOKEN)
























