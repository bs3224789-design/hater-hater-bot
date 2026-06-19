import discord
import os
import re
from flask import Flask
from threading import Thread

# ===== ВЕБ-СЕРВЕР ДЛЯ UPTIMEROBOT =====
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===== БОТ =====
TOKEN = os.environ['TOKEN']
CHANNEL_NAME = 'заявки-бот'

# Роли, которые могут видеть тикеты
ALLOWED_ROLES = [
    1514599381230293094,
    1514614732089331772,
    1514601261612400781,
    1514710792677884125,
    1514613884189802597,
    1514615286551019610,
]

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'✅ Бот {self.user} запущен!')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.channel.name == CHANNEL_NAME:
            content = message.content
            discord_match = re.search(r'Discord: (.+)', content)
            discord_nick = discord_match.group(1).strip() if discord_match else None

            user = None
            if discord_nick:
                for member in message.guild.members:
                    if (member.name.lower() == discord_nick.lower() or 
                        str(member).lower() == discord_nick.lower() or
                        discord_nick.lower() in member.name.lower()):
                        user = member
                        break

            guild = message.guild
            new_channel = await guild.create_text_channel(f'тикет-{message.author.name}')

            mention = user.mention if user else discord_nick or 'Не указан'

            # Отправляем сообщение с тегом
            await new_channel.send(f'📩 **Новая заявка от {mention}!**')
            await new_channel.send(content)

            # ===== НАСТРОЙКА ПРАВ ДОСТУПА =====
            # 1. Закрываем доступ для @everyone
            await new_channel.set_permissions(guild.default_role, read_messages=False)

            # 2. Даём доступ пользователю (если нашли)
            if user:
                await new_channel.set_permissions(user, read_messages=True, send_messages=True)

            # 3. Даём доступ ролям из списка ALLOWED_ROLES
            for role_id in ALLOWED_ROLES:
                role = guild.get_role(role_id)
                if role:
                    await new_channel.set_permissions(role, read_messages=True, send_messages=True)

            # 4. Если есть роль "Admin" — тоже даём доступ
            admin_role = discord.utils.get(guild.roles, name='Admin')
            if admin_role:
                await new_channel.set_permissions(admin_role, read_messages=True, send_messages=True)

client = MyClient(intents=discord.Intents.all())
client.run(TOKEN)
