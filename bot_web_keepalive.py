import os
import discord
import random
from discord.ext import commands
from flask import Flask
from threading import Thread


# --- konfiguracja z ENV ---
TOKEN = os.environ.get("DISCORD_TOKEN")
MODERATORS = [int(x) for x in os.environ.get("MODERATORS", "").split(",") if x.strip()]


if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")


intents = discord.Intents.default()
intents.members = True
intents.message_content = True


bot = commands.Bot(command_prefix='?', intents=intents)


app = Flask("")


@app.route("/")
def home():
    return "Bot alive"


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# uruchom serwer HTTP w osobnym wątku (Render poda PORT automatycznie)
Thread(target=run_flask).start()


@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user}')

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


# --- Ważne wiadomości ---


@bot.command()
async def important(ctx, members: commands.Greedy[discord.Member], *, message):
    if not members:
        await ctx.send("Musisz oznaczyć przynajmniej jednego gracza.")
        return
    notified = []
    for member in members:
        try:
            await member.send(f"Masz nową ważną wiadomość: {message}")
            notified.append(member.name)
        except:
            await ctx.send(f"Nie mogę wysłać wiadomości do {member.name}.")
    if notified:
        await ctx.send(f"Gracze {', '.join(notified)} zostali powiadomieni jako ważne.")


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


# --- Pomoc i zasady ---


@bot.command()
async def help(ctx):
    help_text = """
**Lista komend bota**


Moderacja:
- `?warn @user [powód]` – ostrzeżenie
- `?mute @user [powód]` – wycisza użytkownika
- `?unmute @user` – cofa wyciszenie


 Informacyjne:
- `?important @user [wiadomość]` – wysyła ważną wiadomość
- `?rules` – pokazuje zasady serwera


Zabawa:
- `?roll [sides]` – rzut kostką (domyślnie 1–100)
- `?coinflip` – rzut monetą
- `?8ball [pytanie]` – magiczna kula


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


# --- Ping ---


@bot.command()
async def ping(ctx):
    await ctx.send(" Pong! Bot działa.")

# start bota (discord.py run blokuje wątek główny — Flask już działa w osobnym wątku)
bot.run(TOKEN)



