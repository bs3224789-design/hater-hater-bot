import discord
import os
import re
from flask import Flask
from threading import Thread
from discord.ui import Button, View

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

TOKEN = os.environ['TOKEN']
CHANNEL_NAME = 'заявки-бот'

# ===== КАТЕГОРИЯ ПО ИМЕНИ =====
CATEGORY_NAME = 'ticket'

# ===== ID КАНАЛА ДЛЯ КНОПКИ =====
APPLY_CHANNEL_ID = 1514619992430346240

ALLOWED_ROLES = [
    1514599381230293094,
    1514614732089331772,
    1514601261612400781,
    1514710792677884125,
    1514613884189802597,
    1514615286551019610,
]

processed_messages = set()

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'✅ Бот {self.user} запущен!')
        
        # ===== ОТПРАВЛЯЕМ СООБЩЕНИЕ С КНОПКОЙ В КАНАЛ =====
        channel = self.get_channel(APPLY_CHANNEL_ID)
        if channel:
            # Проверяем, есть ли уже такое сообщение (чтобы не дублировать)
            async for message in channel.history(limit=10):
                if message.author == self.user and message.components:
                    return  # Если уже есть — выходим
            
            embed = discord.Embed(
                title="📩 Подать заявку в семью Хейтер",
                description=(
                    "Нажми на кнопку ниже, чтобы получить персональную ссылку для заполнения заявки.\n\n"
                    "🔒 **Ссылка будет привязана к твоему Discord ID**"
                ),
                color=0x5865F2
            )
            embed.set_footer(text="Семья Хейтер | GTA 5 RP")
            
            view = View()
            view.add_item(Button(
                label="🔗 Сгенерировать ссылку",
                style=discord.ButtonStyle.primary,
                custom_id="generate_link"
            ))
            
            await channel.send(embed=embed, view=view)
            print(f'✅ Сообщение с кнопкой отправлено в канал {channel.name}')
        else:
            print(f'❌ Канал с ID {APPLY_CHANNEL_ID} не найден!')

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            if interaction.data.get("custom_id") == "generate_link":
                user_id = interaction.user.id
                link = f"https://hater-tickets.netlify.app/?user={user_id}"
                
                embed = discord.Embed(
                    title="🔗 Твоя ссылка для заявки",
                    description=(
                        f"Перейди по ссылке, чтобы заполнить заявку:\n\n"
                        f"{link}\n\n"
                        "⚠️ **Важно:** Ссылка привязана к твоему Discord ID. Не передавай её другим."
                    ),
                    color=0x5865F2
                )
                embed.set_footer(text="Семья Хейтер | GTA 5 RP")
                
                try:
                    await interaction.user.send(embed=embed)
                    await interaction.response.send_message(
                        "✅ Ссылка отправлена тебе в **личные сообщения**!",
                        ephemeral=True
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ У тебя закрыты личные сообщения на сервере! "
                        "Открой их в настройках Discord и попробуй снова.",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        "❌ Произошла ошибка. Попробуй позже.",
                        ephemeral=True
                    )
                    print(f'❌ Ошибка: {e}')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.id in processed_messages:
            return
        if message.channel.name == CHANNEL_NAME:
            processed_messages.add(message.id)
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
            
            category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
            
            if category is None:
                category = await guild.create_category(CATEGORY_NAME)
                await category.set_permissions(guild.default_role, read_messages=False)
                for role_id in ALLOWED_ROLES:
                    role = guild.get_role(role_id)
                    if role:
                        await category.set_permissions(role, read_messages=True, connect=True)

            new_channel = await guild.create_text_channel(
                f'тикет-{message.author.name}',
                category=category
            )

            mention = user.mention if user else discord_nick or 'Не указан'

            await new_channel.send(f'📩 **Новая заявка от {mention}!**')
            await new_channel.send(content)

            await new_channel.set_permissions(guild.default_role, read_messages=False)

            if user:
                await new_channel.set_permissions(user, read_messages=True, send_messages=True)

            for role_id in ALLOWED_ROLES:
                role = guild.get_role(role_id)
                if role:
                    await new_channel.set_permissions(role, read_messages=True, send_messages=True)

            admin_role = discord.utils.get(guild.roles, name='Admin')
            if admin_role:
                await new_channel.set_permissions(admin_role, read_messages=True, send_messages=True)

client = MyClient(intents=discord.Intents.all())
client.run(TOKEN)
