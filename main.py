import discord
import os
import re
from flask import Flask
from threading import Thread
from discord.ui import Button, View

# -------------------- Flask для поддержания жизни --------------------
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# -------------------- Конфигурация --------------------
TOKEN = os.environ.get('TOKEN')
if not TOKEN:
    print("❌ Токен не найден! Добавь переменную TOKEN на Railway.")
    exit(1)

# ID канала, куда вебхук отправляет заявки
APPLY_CHANNEL_ID = 1514619992430346240   # замените на свой, если нужно

# Название категории для тикетов
CATEGORY_NAME = 'ticket'

# Роли, которые могут управлять тикетами (ID)
ALLOWED_ROLES = [
    1514599381230293094,
    1514614732089331772,
    1514601261612400781,
    1514710792677884125,
    1514613884189802597,
    1514615286551019610,
]

# Множество для предотвращения повторной обработки (в памяти)
processed_messages = set()

# -------------------- Кнопки для тикета --------------------
class TicketActionsView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._has_permission(interaction):
            await interaction.response.send_message("❌ У тебя нет прав закрывать тикеты!", ephemeral=True)
            return
        await interaction.channel.delete()
        await interaction.response.send_message("✅ Тикет успешно закрыт!", ephemeral=True)

    @discord.ui.button(label="📋 Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="take_ticket")
    async def take_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._has_permission(interaction):
            await interaction.response.send_message("❌ У тебя нет прав брать тикеты!", ephemeral=True)
            return
        old_name = interaction.channel.name
        new_name = f"рассматривает-{interaction.user.name}"
        await interaction.channel.edit(name=new_name)
        await interaction.response.send_message(
            f"✅ Тикет **{old_name}** взят на рассмотрение **{interaction.user.mention}**!",
            ephemeral=False
        )

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        for role_id in ALLOWED_ROLES:
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                return True
        return False

# -------------------- Кнопка для генерации ссылки --------------------
class LinkButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔗 Сгенерировать ссылку", style=discord.ButtonStyle.primary, custom_id="generate_link")
    async def generate_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_tag = str(interaction.user)
        link = f"https://hater-website.vercel.app/?user={user_tag}"
        embed = discord.Embed(
            title="🔗 Твоя ссылка для заявки",
            description=f"Перейди по ссылке, чтобы заполнить заявку:\n\n{link}\n\n⚠️ **Важно:** Ссылка привязана к твоему Discord нику. Не передавай её другим.",
            color=0x5865F2
        )
        embed.set_footer(text="Семья Хейтер | GTA 5 RP")
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("✅ Ссылка отправлена тебе в **личные сообщения**!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Произошла ошибка. Попробуй позже.", ephemeral=True)
            print(f'❌ Ошибка отправки ссылки: {e}')

# -------------------- Основной клиент --------------------
class MyClient(discord.Client):
    async def on_ready(self):
        print(f'✅ Бот {self.user} запущен!')
        channel = self.get_channel(APPLY_CHANNEL_ID)
        if not channel:
            print(f'❌ Канал с ID {APPLY_CHANNEL_ID} не найден!')
            return

        # Очищаем старые сообщения бота
        async for msg in channel.history(limit=20):
            if msg.author == self.user:
                await msg.delete()

        embed = discord.Embed(
            title="📩 Подать заявку в семью Хейтер",
            description="Нажми на кнопку ниже, чтобы получить персональную ссылку для заполнения заявки.",
            color=0x5865F2
        )
        embed.set_footer(text="Семья Хейтер | GTA 5 RP")
        view = LinkButtonView()
        await channel.send(embed=embed, view=view)
        print(f'✅ Сообщение с кнопкой отправлено в канал {channel.name}')

    async def on_message(self, message):
        # Игнорируем свои сообщения и уже обработанные
        if message.author == self.user or message.id in processed_messages:
            return

        # Реагируем только на сообщения в канале для заявок (по ID)
        if message.channel.id != APPLY_CHANNEL_ID:
            return

        processed_messages.add(message.id)
        content = message.content

        # --- Парсим поля ---
        def extract_field(label):
            # Ищем "Label: значение" с учётом возможного "1. " перед значением
            pattern = rf'{re.escape(label)}:\s*(.+)'
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                # Убираем префикс "1. " или "2. " и т.п., если он есть
                cleaned = re.sub(r'^\d+\.\s*', '', raw)
                return cleaned
            return None

        # Извлекаем нужные данные
        discord_username = extract_field('Discord')
        nickname = extract_field('Игровой ник')
        name = extract_field('Имя')
        age = extract_field('Возраст')
        recoil = extract_field('Откаты стрельбы')
        family_history = extract_field('История семей')
        user_message = extract_field('Сообщение')

        # Если Discord не найден, пробуем взять никнейм как запасной вариант
        if not discord_username and nickname:
            discord_username = nickname

        # Пытаемся найти участника на сервере
        user = None
        if discord_username:
            for member in message.guild.members:
                if str(member) == discord_username or member.name.lower() == discord_username.lower():
                    user = member
                    break

        # --- Создаём тикет-канал ---
        guild = message.guild
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(CATEGORY_NAME)
            await category.set_permissions(guild.default_role, read_messages=False)
            for role_id in ALLOWED_ROLES:
                role = guild.get_role(role_id)
                if role:
                    await category.set_permissions(role, read_messages=True, connect=True)

        # Имя канала – используем ник заявителя, если нашли, иначе – имя отправителя (вебхук)
        if user:
            channel_name = f'тикет-{user.name}'
        elif discord_username:
            channel_name = f'тикет-{discord_username}'
        else:
            channel_name = f'тикет-{message.author.name}'

        # Убеждаемся, что имя не слишком длинное (Discord ограничение - 100 символов)
        if len(channel_name) > 100:
            channel_name = channel_name[:100]

        new_channel = await guild.create_text_channel(channel_name, category=category)

        # Устанавливаем права доступа
        await new_channel.set_permissions(guild.default_role, read_messages=False)
        if user:
            await new_channel.set_permissions(user, read_messages=True, send_messages=True)
        for role_id in ALLOWED_ROLES:
            role = guild.get_role(role_id)
            if role:
                await new_channel.set_permissions(role, read_messages=True, send_messages=True)

        # Дополнительно даём доступ роли Admin, если есть
        admin_role = discord.utils.get(guild.roles, name='Admin')
        if admin_role:
            await new_channel.set_permissions(admin_role, read_messages=True, send_messages=True)

        # --- Отправляем сообщение в тикет ---
        mention = user.mention if user else discord_username or 'Не указан'
        await new_channel.send(f'📩 **Новая заявка от {mention}!**')

        # Формируем красивое сообщение с заявкой
        embed_ticket = discord.Embed(
            title="📋 Данные заявки",
            color=0x00ff00,
            timestamp=message.created_at
        )
        embed_ticket.add_field(name="Имя", value=name or "Не указано", inline=True)
        embed_ticket.add_field(name="Возраст", value=age or "Не указан", inline=True)
        embed_ticket.add_field(name="Discord", value=discord_username or "Не указан", inline=True)
        embed_ticket.add_field(name="Игровой ник", value=nickname or "Не указан", inline=True)
        embed_ticket.add_field(name="Откаты стрельбы", value=recoil or "Не указаны", inline=True)
        embed_ticket.add_field(name="История семей", value=family_history or "Не указана", inline=True)
        embed_ticket.add_field(name="Сообщение", value=user_message or "Нет", inline=False)
        embed_ticket.set_footer(text=f"Заявка от {message.author.name}")

        await new_channel.send(embed=embed_ticket)

        # Кнопки управления тикетом
        view = TicketActionsView()
        await new_channel.send(
            "🔽 **Действия с тикетом:**",
            view=view
        )

        print(f'✅ Создан тикет {new_channel.name} для {discord_username or "неизвестного пользователя"}')

# -------------------- Запуск --------------------
if __name__ == "__main__":
    keep_alive()                # Запускаем Flask-сервер для Railway
    client = MyClient(intents=discord.Intents.all())
    client.run(TOKEN)
