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

TOKEN = os.environ.get('TOKEN')
if not TOKEN:
    print("❌ Токен не найден! Добавь переменную TOKEN на Railway.")
    exit(1)

CHANNEL_NAME = 'заявки-бот'
CATEGORY_NAME = 'ticket'
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

class TicketActionsView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not any(interaction.guild.get_role(role_id) in interaction.user.roles for role_id in ALLOWED_ROLES):
            await interaction.followup.send("❌ У тебя нет прав закрывать тикеты!", ephemeral=True)
            return

        channel = interaction.channel
        try:
            # Сначала отправляем подтверждение, потом удаляем канал
            await interaction.followup.send("✅ Тикет успешно закрыт!", ephemeral=True)
            await channel.delete()
        except discord.NotFound:
            # Канал уже удалён
            await interaction.followup.send("❌ Тикет уже закрыт.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Ошибка при закрытии тикета.", ephemeral=True)
            print(f"Ошибка close_ticket: {e}")

    @discord.ui.button(label="📋 Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="take_ticket")
    async def take_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        if not any(interaction.guild.get_role(role_id) in interaction.user.roles for role_id in ALLOWED_ROLES):
            await interaction.followup.send("❌ У тебя нет прав брать тикеты на рассмотрение!", ephemeral=True)
            return

        channel = interaction.channel
        old_name = channel.name

        if old_name.startswith("рассматривает-"):
            await interaction.followup.send("❌ Этот тикет уже рассматривается!", ephemeral=True)
            return

        new_name = f"рассматривает-{interaction.user.name}"
        try:
            await channel.edit(name=new_name)
        except Exception as e:
            await interaction.followup.send("❌ Не удалось переименовать канал.", ephemeral=True)
            print(f"Ошибка переименования: {e}")
            return

        # Уведомление создателя
        topic = channel.topic
        if topic and topic.startswith("Создатель: "):
            try:
                creator_id = int(topic.split(": ")[1])
                creator = interaction.guild.get_member(creator_id)
                if creator is None:
                    try:
                        creator = await interaction.guild.fetch_member(creator_id)
                    except discord.NotFound:
                        creator = None
                if creator:
                    try:
                        await creator.send(f"📩 **Ваша заявка** была взята на рассмотрение **{interaction.user.mention}** в канале {channel.mention}.")
                    except discord.Forbidden:
                        await interaction.followup.send("⚠️ Не удалось отправить уведомление создателю (закрыты ЛС).", ephemeral=True)
                else:
                    await interaction.followup.send("⚠️ Создатель заявки не найден на сервере.", ephemeral=True)
            except Exception as e:
                print(f"Не удалось отправить уведомление: {e}")
                await interaction.followup.send("❌ Ошибка при отправке уведомления.", ephemeral=True)

        await interaction.followup.send(
            f"✅ Тикет **{old_name}** взят на рассмотрение **{interaction.user.mention}**!",
            ephemeral=False
        )

    @discord.ui.button(label="🔄 Сняться с рассмотрения", style=discord.ButtonStyle.secondary, custom_id="untake_ticket")
    async def untake_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        if not any(interaction.guild.get_role(role_id) in interaction.user.roles for role_id in ALLOWED_ROLES):
            await interaction.followup.send("❌ У тебя нет прав сниматься с рассмотрения!", ephemeral=True)
            return

        channel = interaction.channel
        current_name = channel.name

        if not current_name.startswith("рассматривает-"):
            await interaction.followup.send("❌ Этот тикет сейчас не рассматривается!", ephemeral=True)
            return

        topic = channel.topic
        if not topic or not topic.startswith("Создатель: "):
            await interaction.followup.send("❌ Не удалось определить создателя тикета.", ephemeral=True)
            return

        creator_id_str = topic.split(": ")[1]
        creator = None
        try:
            creator_id = int(creator_id_str)
            creator = interaction.guild.get_member(creator_id)
            if creator is None:
                try:
                    creator = await interaction.guild.fetch_member(creator_id)
                except discord.NotFound:
                    creator = None
        except:
            pass

        new_name = f"тикет-{creator.name if creator else 'unknown'}"
        try:
            await channel.edit(name=new_name)
        except Exception as e:
            await interaction.followup.send("❌ Не удалось переименовать канал.", ephemeral=True)
            print(f"Ошибка переименования: {e}")
            return

        if creator:
            try:
                await creator.send(f"🔄 Рассмотрение вашей заявки было отменено сотрудником {interaction.user.mention}.")
            except discord.Forbidden:
                await interaction.followup.send("⚠️ Не удалось отправить уведомление создателю (закрыты ЛС).", ephemeral=True)
            except Exception as e:
                print(f"Не удалось отправить уведомление об отмене: {e}")

        await interaction.followup.send(
            f"✅ Ты снялся с рассмотрения тикета **{current_name}**.",
            ephemeral=False
        )

class LinkButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🖇️ Сгенерировать ссылку",
        style=discord.ButtonStyle.primary,
        custom_id="generate_link"
    )
    async def generate_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        user_name = interaction.user.name
        user_discriminator = interaction.user.discriminator
        user_tag = f"{user_name}#{user_discriminator}" if user_discriminator != '0' else user_name

        link = f"https://hater-website.vercel.app/?user={user_tag}"

        embed = discord.Embed(
            title="🔗 Твоя ссылка для заявки",
            description=(
                f"Перейди по ссылке, чтобы заполнить заявку:\n\n"
                f"{link}\n\n"
                "⚠️ **Важно:** Ссылка привязана к твоему Discord нику. Не передавай её другим."
            ),
            color=0x5865F2
        )
        embed.set_thumbnail(url="https://i.postimg.cc/KvQ2CZ82/3dgifmaker48342.gif")
        embed.set_footer(text="Семья Хейтер | GTA 5 RP")

        try:
            await interaction.user.send(embed=embed)
            await interaction.followup.send("✅ Ссылка отправлена тебе в **личные сообщения**!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Произошла ошибка. Попробуй позже.", ephemeral=True)
            print(f'❌ Ошибка: {e}')

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'✅ Бот {self.user} запущен!')

        channel = self.get_channel(APPLY_CHANNEL_ID)
        if channel:
            async for message in channel.history(limit=20):
                if message.author == self.user:
                    await message.delete()

            embed = discord.Embed(
                title="📩 Подать заявку в семью Хейтер",
                description="Нажми на кнопку ниже, чтобы получить персональную ссылку для заполнения заявки.",
                color=0x5865F2
            )
            embed.set_thumbnail(url="https://i.postimg.cc/KvQ2CZ82/3dgifmaker48342.gif")
            embed.set_footer(text="Семья Хейтер | GTA 5 RP")

            view = LinkButtonView()
            await channel.send(embed=embed, view=view)
            print(f'✅ Сообщение с кнопкой отправлено в канал {channel.name}')
        else:
            print(f'❌ Канал с ID {APPLY_CHANNEL_ID} не найден!')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.id in processed_messages:
            return
        if message.channel.name == CHANNEL_NAME:
            processed_messages.add(message.id)
            content = message.content

            discord_match = re.search(r'Discord: (.+)', content)
            discord_username = discord_match.group(1).strip() if discord_match else None

            if not discord_username:
                nickname_match = re.search(r'Игровой ник: (.+)', content)
                discord_username = nickname_match.group(1).strip() if nickname_match else None

            user = None
            if discord_username:
                for member in message.guild.members:
                    if str(member) == discord_username:
                        user = member
                        break
                    if member.name.lower() == discord_username.lower():
                        user = member
                        break
                    if discord_username.lower() in member.name.lower():
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

            await new_channel.edit(topic=f"Создатель: {message.author.id}")

            mention = user.mention if user else discord_username or 'Не указан'

            view = TicketActionsView()
            await new_channel.send(f'📩 **Новая заявка от {mention}!**')
            await new_channel.send(content)
            await new_channel.send("🔽 **Действия с тикетом:**", view=view)

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
