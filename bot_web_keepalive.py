import os
import discord
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


# -------- twoje komendy (przykład) --------
# wklej tu dokładnie swoje funkcje warn, important, kick, mute, shield, ping
# poniżej skrócona wersja — wklej pełne definicje jakie masz lokalnie


# ?warn - ostrzeżenie (tylko moderatorzy)
@bot.command()
async def warn(ctx, member: discord.Member, *, reason):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie wolno używać tego polecenia!")
        return
    try:
        await member.send("Panie, zostałeś ostrzeżony! Przypominamy o konieczności przestrzegania zasad serwera! Kolejne ostrzeżenia mogą skutkować wyciszeniem lub wyrzuceniem z serwera!")
    except:
        await ctx.send("Nie mogę wysłać PW do tego użytkownika.")
    await ctx.send(f"{member.name} został ostrzeżony. ({reason})")




# ?important - ważna wiadomość (dla wszystkich)
@bot.command()
async def important(ctx, member: discord.Member, *, message):
    try:
        await member.send("Masz nowe wiadomości oznaczone jako ważne. Przeczytaj je!")
    except:
        await ctx.send("Cannot DM this user.")
    await ctx.send(f"{member.name} zostało zgłoszone jako ważne. ({message})")




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




# ?mute - wyciszenie (tylko moderatorzy)
@bot.command()
async def mute(ctx, member: discord.Member, *, reason="No reason provided"):
    if ctx.author.id not in MODERATORS:
        await ctx.send("Nie wolno używać tego polecenia!")
        return


    # Znajdź rolę "Muted"
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Role 'Muted' does not exist. Please create it first.")
        return


    try:
        await member.add_roles(muted_role, reason=reason)
        await ctx.send(f"{member.name} został wyciszony. ({reason})")
    except:
        await ctx.send("Nie mogę wyciszyć tego użytkownika.")




# ?shield - dostępne dla wszystkich
@bot.command()
async def shield(ctx, member: discord.Member):
    try:
        await ctx.send(f"{member.mention} gracz został poinformowany o braku tarczy")
        await member.send("Użyj tarczy! Wróg już nadciąga!")
    except:
        await ctx.send("Nie mogę wysłać PW do tego użytkownika.")




# Komenda testowa ?ping
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


# start bota (discord.py run blokuje wątek główny — Flask już działa w osobnym wątku)
bot.run(TOKEN)