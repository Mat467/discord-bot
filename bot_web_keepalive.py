import os
import discord
import random
import io
import asyncio
import aiohttp
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread

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

if not TOKEN:
    raise RuntimeError("Brak DISCORD_TOKEN w zmiennych środowiskowych")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='?', intents=intents, help_command=None)

# ---- Flask ping ----
app = Flask("")

@app.route("/")
def home():
    return "Bot alive"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()

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

session: aiohttp.ClientSession = None  # globalna sesja HTTP

async def send_christmas_embed(channel):
    """Wysyła losowy embed świąteczny do danego kanału z Pexels."""
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
        await session.close()
        session = None
        return  # sukces, kończymy pętlę

# ---- Pętla świąteczna co 8 godzin ----
CHANNEL_ID = 1437924798645928106  # <-- podaj ID swojego kanału

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

@bot.event
async def on_ready():
    global session
    print(f'Bot uruchomiony jako {bot.user}')

    if session is None or session.closed:
        session = aiohttp.ClientSession(timeout=HTTP_TIMEOUT)
    # Uruchamiamy pętlę tylko raz (on_ready może być wywołane wiele razy przy re-connect)
    if not christmas_loop.is_running():
        christmas_loop.start()

@bot.event
async def on_member_join(member):
    # Wysyła powitanie na kanale o nazwie "powitania"
    channel = discord.utils.get(member.guild.text_channels, name="powitania")
    if channel:
        await channel.send(f"🎉 Witamy nowego członka: {member.mention}! Dajcie mu serduszko ❤️")

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

# --- Bezpieczne zamknięcie globalnej sesji aiohttp przy wyłączeniu bota ---
@bot.event
async def on_disconnect():
    global session
    if session and not session.closed:
        await session.close()
        print("🌐 Globalna sesja aiohttp została zamknięta.")


DEAF_PROPHECIES = [
    "Przeznaczenie spojrzało… i przewróciło oczami.",
    "Los uznał, że to nie ta linia czasowa.",
    "Kosmos mówi: „meh” nie tym razem.",
    "Gwiazdy się ustawiły… przeciwko tobie.",
    "Dziś nie wygrywasz. Nawet w Monopoly.",
    "Masz szczęście. Tylko nie dziś.",
    "Wszechświat nacisnął „pomiń”, więc zagraj jeszcze raz..",
    "System wykrył brak aury zwycięzcy.",
    "Automat stwierdził: próbuj później."
]

MINI_PROPHECIES = [
    "Ktoś dziś zapyta o coś oczywistego.",
    "Twój czajnik będzie działał z determinacją.",
    "Za godzinę przypomnisz sobie coś żenującego.",
    "Jutro też będzie jutro.",
    "Twoja lodówka otworzy się przynajmniej raz.",
    "O 3:17 przypomnisz sobie coś żenującego z 2014.",
    "Ktoś dziś zapyta „co robicie”.",
    "Twoje WiFi przetrwa kolejny dzień.",
    "Herbata wystygnie szybciej niż planowałeś.",
    "Zobaczysz powiadomienie, które nie jest do ciebie.",
    "Twój telefon będzie w twojej kieszeni. Prawdopodobnie.",
    "Ktoś powie „to tylko 5 minut” i nie będzie to 5 minut.",
    "Dziś zjesz coś. To będzie jedzenie."
]

JACKPOT_PROPHECIES = [
    "Dziś w nocy będzie ciemno.",
    "Twoje skarpetki nie będą parą. I nigdy nie były.",
    "Klikniesz coś, czego nie trzeba było klikać.",
    "Wiosna przyniesie… więcej wiosny.",
    "Za 6 godzin powiesz „nie no, serio?”.",
    "Jesteś główną postacią… w czyjejś historii pobocznej.",
    "Przyszłość przewiduje… więcej przyszłości.",
    "Jutro wstaniesz. To nie groźba.",
    "Twoje przeznaczenie ma opóźnienie.",
    "W tym tygodniu powiesz „dobra, od jutra”.",
    "Wszechświat mrugnął. Nikt nie wie czemu.",
    "Dziś unikniesz jednej drobnej katastrofy. Nie dowiesz się której.",
    "Masz w sobie potencjał. Leży gdzieś pod kanapą.",
    "Twoja legenda zacznie się… kiedyś.",
    "Serwer będzie dziś działał. Szokujące.",
    "Twój przyszły „ja” mówi: ogarnij się.",
    "Wszechświat wyśle Ci tajemniczy znak."
]


class CasinoView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.button(label="🎰 ZAKRĘĆ", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message(
                "To nie twoje kasyno. Nie dotykaj cudzej ruletki.",
                ephemeral=True
            )
            return

        roll = random.randint(1, 100)

        if roll <= 50:  # 50% porażka
            prophecy = random.choice(DEAF_PROPHECIES)
            result_text = f"💀 **{interaction.user.mention}, tym razem porażka!**\n: {prophecy} ❌"
        elif roll <= 80:  # 30% mini
            prophecy = random.choice(MINI_PROPHECIES)
            result_text = f"✨ **{interaction.user.mention} wygrał!**\nOto twoja przepowiednia! Przepowiadam, że:\n🔮 {prophecy} 🌟"
        else:  # 20% jackpot
            prophecy = random.choice(JACKPOT_PROPHECIES)
            result_text = f"💥 **JACKPOT!!! {interaction.user.mention}** 💥\nGratulacje! Oto twoja przepowiednia premium! Przepowiadam, że: \n🎇🔮 {prophecy} 🎇"

        button.disabled = True
        await interaction.response.edit_message(content=result_text, view=self)
        self.stop()


@bot.command(name="kasyno")
async def kasyno(ctx):
    view = CasinoView(ctx.author)
    embed = discord.Embed(
        title="🎰 Wiosenne Kasyno Chaosu",
        description=f"@{ctx.author.display_name} – kliknij przycisk i sprawdź, czy los ma dziś dobry humor.",
        color=0xF1C40F
    )
    await ctx.send(embed=embed, view=view)

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
    "Pong… a w twoim telefonie nic się nie zmieniło."
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
        await ctx.send("Nie wolno używać tego polecenia!")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member.name} został wyrzucony. ({reason})")
    except discord.Forbidden:
        await ctx.send("Nie mam uprawnień, by wyrzucić tego użytkownika.")
    except discord.HTTPException:
        await ctx.send("Nie udało się wyrzucić tego użytkownika.")

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

# --- Zabawa ---
@bot.command()
async def roll(ctx, sides: int = 100):
    try:
        result = random.randint(1, sides)
        await ctx.send(f"🎲 {ctx.author.name} rzucił kostką (1–{sides}) i wypadło **{result}**")
    except Exception as e:
        print(f"[roll] {e}")
        await ctx.send("Wystąpił błąd podczas rzutu kostką.")

@bot.command()
async def coinflip(ctx):
    result = random.choice(["orzeł", "reszka"])
    await ctx.send(f"{ctx.author.name} rzucił monetą: **{result}**")

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

@bot.command(
    name="8ballfun",
    aliases=["ballfun", "🎱fun"]
)
async def eightballfun(ctx, *, question: str):
    """Sarkastyczny 8ball — odpowiedzi pasujące do pytań tak/nie."""
    answer = random.choice(SARCASM_RESPONSES)
    await ctx.send(f"**{ctx.author.display_name} pyta:** {question}\n{answer}")

@bot.command()
async def rps(ctx, choice: str):
    choices = ["kamień", "papier", "nożyce"]
    bot_choice = random.choice(choices)
    choice = choice.lower()
    if choice not in choices:
        await ctx.send("Użyj: `?rps kamień`, `?rps papier` albo `?rps nożyce`.")
        return
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

# --- Komendy pomocy i informacyjne ---
@bot.command(name="print")
async def echo(ctx, *, text: str):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(text)

@bot.command()
async def rules(ctx):
    rules_text = """
**Zasady serwera:**

1️⃣ Szanuj innych – zero obrażania i wyzwisk.  
2️⃣ Brak polityki i religii – nie miejsce na takie dyskusje.  
3️⃣ Nie spamuj i nie flooduj wiadomości.  
4️⃣ Zakaz reklamowania innych serwerów/stron.  
5️⃣ Nie używaj cheatów ani exploitów w grach.  
6️⃣ Trzymaj się tematów kanałów.  
7️⃣ Słuchaj administracji i moderatorów.  
8️⃣ Zakaz udostępniania treści NSFW i nielegalnych.  
9️⃣ Używaj języka polskiego lub angielskiego (jeśli ustalono).  
🔟 Pamiętaj – baw się dobrze i wspieraj klimat serwera!
"""
    await ctx.send(rules_text)

@bot.command()
async def help(ctx):
    help_text = """
**Lista komend bota**

__Moderacja:__  
• `?warn @user [powód]` – wysyła ostrzeżenie  
• `?mute @user [powód]` – wycisza użytkownika  
• `?unmute @user` – cofa wyciszenie  
• `?kick @user [powód]` – usuwa z serwera  

__Informacyjne:__  
• `?important @user/rola [wiadomość]` – wysyła ważną wiadomość (DM)  
• `?rules` – pokazuje zasady serwera  
• `?shield @user` – informuje o braku tarczy (DM)  
• `?spamshield @user [ilość, max 10]` – spam DM z tarczami  
• `?kontrlist` – wysyła listę konter jako embed  
• `?print [wiadomość]` – bot powtórzy wiadomość  

__Zabawa:__  
• `?roll [sides]` – rzut kostką (domyślnie 1–100)  
• `?coinflip` – rzut monetą  
• `?8ball [pytanie]` – magiczna kula (prosta)  
• `?8ballfun [pytanie]` – rozbudowana magiczna kula  
• `?cat` – losowy kotek (embed)  
• `?rps [kamień/papier/nożyce]` – gra Kamień/Papier/Nożyce  
• `?specjal` – wysyła obrazek tematyczny
__Narzędzia:__  
• `?ping` – sprawdza czy bot działa  
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
async def specjal(ctx):
    await send_christmas_embed(ctx.channel)
    
ACTIVE_THEMES = CHRISTMAS_THEMES

# Uruchomienie bota
bot.run(TOKEN)
















































