import discord
import os
import re
from flask import Flask
from threading import Thread
from discord.ui import Button, View, Modal, TextInput

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

# Роли, которые бот будет автоматически тегать при создании нового тикета
MENTION_ROLES = [
    1514710792677884125,
    1514613884189802597,
    1514615286551019610,
]

processed_messages = set()


def get_creator_id_from_topic(channel: discord.TextChannel):
    """Достаём ID создателя тикета из темы канала."""
    topic = channel.topic
    if not topic or not topic.startswith("Создатель: "):
        return None
    try:
        return int(topic.split(": ")[1].strip())
    except (IndexError, ValueError):
        return None


def has_allowed_role(interaction: discord.Interaction) -> bool:
    return any(
        interaction.guild.get_role(role_id) in interaction.user.roles
        for role_id in ALLOWED_ROLES
    )


class CloseReasonModal(Modal, title="Закрытие тикета"):
    reason = TextInput(
        label="Причина закрытия",
        style=discord.TextStyle.paragraph,
        placeholder="Опиши причину закрытия тикета...",
        max_length=500,
        required=True,
    )

    def __init__(self, channel: discord.TextChannel, creator_id: int | None):
        super().__init__()
        self.channel = channel
        self.creator_id = creator_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Пытаемся отправить автору заявки уведомление о закрытии
        if self.creator_id:
            try:
                user = interaction.guild.get_member(self.creator_id)
                if user is None:
                    user = await interaction.client.fetch_user(self.creator_id)
                if user:
                    embed = discord.Embed(
                        title="🔒 Ваша заявка была закрыта",
                        description=f"**Причина:** {self.reason.value}",
                        color=0xE74C3C
                    )
                    embed.set_footer(text="Семья Хейтер | GTA 5 RP")
                    await user.send(embed=embed)
            except discord.Forbidden:
                print("⚠️ Не удалось отправить DM автору заявки (закрыты ЛС).")
            except Exception as e:
                print(f"⚠️ Ошибка отправки DM при закрытии: {e}")

        try:
            await interaction.followup.send("✅ Тикет успешно закрыт!", ephemeral=True)
            await self.channel.delete()
        except discord.NotFound:
            await interaction.followup.send("❌ Тикет уже закрыт.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Ошибка при закрытии тикета.", ephemeral=True)
            print(f"Ошибка close_ticket (modal): {e}")


class TicketActionsView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_allowed_role(interaction):
            await interaction.response.send_message("❌ У тебя нет прав закрывать тикеты!", ephemeral=True)
            return

        channel = interaction.channel
        creator_id = get_creator_id_from_topic(channel)
        modal = CloseReasonModal(channel=channel, creator_id=creator_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📋 Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="take_ticket")
    async def take_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        if not has_allowed_role(interaction):
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
        except discord.NotFound:
            await interaction.followup.send("❌ Канал уже не существует.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send("❌ Не удалось переименовать канал.", ephemeral=True)
            print(f"Ошибка переименования: {e}")
            return

        await interaction.followup.send(
            f"✅ Тикет **{old_name}** взят на рассмотрение **{interaction.user.mention}**!",
            ephemeral=False
        )

        # Уведомляем автора заявки в ЛС
        creator_id = get_creator_id_from_topic(channel)
        if creator_id:
            try:
                user = interaction.guild.get_member(creator_id)
                if user is None:
                    user = await interaction.client.fetch_user(creator_id)
                if user:
                    embed = discord.Embed(
                        title="📋 Ваша заявка взята на рассмотрение",
                        description=f"Модератор **{interaction.user.name}** начал рассматривать вашу заявку.",
                        color=0x5865F2
                    )
                    embed.set_footer(text="Семья Хейтер | GTA 5 RP")
                    await user.send(embed=embed)
            except discord.Forbidden:
                print("⚠️ Не удалось отправить DM автору заявки (закрыты ЛС).")
            except Exception as e:
                print(f"⚠️ Ошибка отправки DM при взятии на рассмотрение: {e}")

    @discord.ui.button(label="🔄 Сняться с рассмотрения", style=discord.ButtonStyle.secondary, custom_id="untake_ticket")
    async def untake_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        if not has_allowed_role(interaction):
            await interaction.followup.send("❌ У тебя нет прав сниматься с рассмотрения!", ephemeral=True)
            return

        channel = interaction.channel
        current_name = channel.name

        if not current_name.startswith("рассматривает-"):
            await interaction.followup.send("❌ Этот тикет сейчас не рассматривается!", ephemeral=True)
            return

        creator_id = get_creator_id_from_topic(channel)
        if not creator_id:
            await interaction.followup.send("❌ Не удалось определить создателя тикета.", ephemeral=True)
            return

        new_name = f"тикет-{creator_id}"
        try:
            await channel.edit(name=new_name)
        except discord.NotFound:
            await interaction.followup.send("❌ Канал уже не существует.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send("❌ Не удалось переименовать канал.", ephemeral=True)
            print(f"Ошибка переименования: {e}")
            return

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
        # Важно: регистрируем persistent-views заново при каждом старте бота,
        # иначе кнопки в СТАРЫХ тикетах перестают отвечать после рестарта бота
        # (это и была основная причина ошибок на кнопках).
        self.add_view(TicketActionsView())
        self.add_view(LinkButtonView())

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

            # Сохраняем ID создателя в теме (для переименования при снятии и для DM)
            await new_channel.edit(topic=f"Создатель: {message.author.id}")

            mention = user.mention if user else discord_username or 'Не указан'

            # Собираем упоминания ролей, которые нужно затегать при создании тикета
            role_mentions = []
            for role_id in MENTION_ROLES:
                role = guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            roles_text = " ".join(role_mentions)

            view = TicketActionsView()
            await new_channel.send(
                f'📩 **Новая заявка от {mention}!**\n{roles_text}',
                allowed_mentions=discord.AllowedMentions(roles=True, users=True)
            )
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
