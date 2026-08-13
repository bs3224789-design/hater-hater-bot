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

# Ссылка-приглашение, которая отправляется при вызове на обзвон
VOICE_INVITE_LINK = "https://discord.gg/beSwNvqMU4"

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


def get_ticket_channel(interaction: discord.Interaction) -> discord.TextChannel:
    """
    Кнопки теперь живут в приватном треде внутри тикет-канала (чтобы заявитель их не видел).
    Эта функция возвращает НАСТОЯЩИЙ тикет-канал (родителя треда), а не сам тред,
    чтобы переименование/удаление/чтение темы работало с самим тикетом.
    """
    ch = interaction.channel
    if isinstance(ch, discord.Thread):
        return ch.parent
    return ch


async def resolve_user(client: discord.Client, guild: discord.Guild, user_id: int):
    """Пытается найти пользователя всеми доступными способами: кэш -> fetch_member -> fetch_user."""
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        member = await guild.fetch_member(user_id)
        return member
    except (discord.NotFound, discord.HTTPException):
        pass
    try:
        user = await client.fetch_user(user_id)
        return user
    except (discord.NotFound, discord.HTTPException):
        return None


async def send_dm_with_feedback(client: discord.Client, guild: discord.Guild,
                                 user_id: int | None, embed: discord.Embed, context_label: str,
                                 report):
    """
    Отправляет DM пользователю и, если не получилось, зовёт report(text) с причиной —
    чтобы было видно, что пошло не так, без залезания в логи Railway.
    report может быть channel.send или interaction.followup.send (ephemeral).
    """
    if not user_id:
        await report(f"⚠️ Не удалось отправить уведомление ({context_label}): не найден ID создателя в теме канала.")
        return

    user = await resolve_user(client, guild, user_id)
    if not user:
        await report(f"⚠️ Не удалось отправить уведомление ({context_label}): пользователь <@{user_id}> не найден на сервере.")
        return

    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        await report(
            f"⚠️ Не удалось отправить ЛС пользователю {user.mention} ({context_label}): "
            f"у него закрыты личные сообщения от участников сервера."
        )
    except Exception as e:
        await report(f"⚠️ Не удалось отправить уведомление ({context_label}): ошибка {e}")
        print(f"Ошибка DM ({context_label}): {e}")


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
        embed = discord.Embed(
            title="🔒 Ваша заявка была закрыта",
            description=f"**Причина:** {self.reason.value}",
            color=0xE74C3C
        )
        embed.set_footer(text="Семья Хейтер | GTA 5 RP")

        async def report(text):
            await interaction.followup.send(text, ephemeral=True)

        await send_dm_with_feedback(
            interaction.client, interaction.guild,
            self.creator_id, embed, "закрытие тикета", report
        )

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

        ticket_channel = get_ticket_channel(interaction)
        creator_id = get_creator_id_from_topic(ticket_channel)
        modal = CloseReasonModal(channel=ticket_channel, creator_id=creator_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✅ Рассмотрено", style=discord.ButtonStyle.success, custom_id="mark_reviewed")
    async def mark_reviewed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not has_allowed_role(interaction):
            await interaction.followup.send("❌ У тебя нет прав отмечать тикеты рассмотренными!", ephemeral=True)
            return

        ticket_channel = get_ticket_channel(interaction)
        try:
            await interaction.followup.send("✅ Тикет отмечен как рассмотренный и будет удалён.", ephemeral=True)
            await ticket_channel.delete()
        except discord.NotFound:
            await interaction.followup.send("❌ Тикет уже удалён.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Ошибка при удалении тикета.", ephemeral=True)
            print(f"Ошибка mark_reviewed: {e}")

    @discord.ui.button(label="📞 Вызвать на обзвон", style=discord.ButtonStyle.primary, custom_id="call_to_voice")
    async def call_to_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not has_allowed_role(interaction):
            await interaction.followup.send("❌ У тебя нет прав вызывать на обзвон!", ephemeral=True)
            return

        ticket_channel = get_ticket_channel(interaction)
        creator_id = get_creator_id_from_topic(ticket_channel)

        if not creator_id:
            await interaction.followup.send("⚠️ Не найден ID заявителя в теме канала — некому звонить.", ephemeral=True)
            return

        target_user = await resolve_user(interaction.client, interaction.guild, creator_id)
        if not target_user:
            await interaction.followup.send(f"⚠️ Пользователь <@{creator_id}> не найден на сервере.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📞 Вас вызвали на обзвон!",
            description=f"Пожалуйста, подключайтесь по ссылке ниже:\n{VOICE_INVITE_LINK}",
            color=0x57F287
        )
        embed.set_footer(text="Семья Хейтер | GTA 5 RP")

        try:
            await target_user.send(
                content=target_user.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True)
            )
            await interaction.followup.send(f"✅ Уведомление о звонке отправлено {target_user.mention}!", ephemeral=True)
            await ticket_channel.send(f"📞 {interaction.user.mention} вызвал {target_user.mention} на обзвон.")
        except discord.Forbidden:
            await interaction.followup.send(
                f"⚠️ Не удалось отправить ЛС {target_user.mention}: у него закрыты личные сообщения от участников сервера.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"⚠️ Ошибка при отправке уведомления: {e}", ephemeral=True)
            print(f"Ошибка call_to_voice: {e}")

    @discord.ui.button(label="📋 Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="take_ticket")
    async def take_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not has_allowed_role(interaction):
            await interaction.followup.send("❌ У тебя нет прав брать тикеты на рассмотрение!", ephemeral=True)
            return

        ticket_channel = get_ticket_channel(interaction)
        old_name = ticket_channel.name

        if old_name.startswith("рассматривает-"):
            await interaction.followup.send("❌ Этот тикет уже рассматривается!", ephemeral=True)
            return

        new_name = f"рассматривает-{interaction.user.name}"
        try:
            await ticket_channel.edit(name=new_name)
        except discord.NotFound:
            await interaction.followup.send("❌ Канал уже не существует.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send("❌ Не удалось переименовать канал.", ephemeral=True)
            print(f"Ошибка переименования: {e}")
            return

        await interaction.followup.send(
            f"✅ Тикет **{old_name}** взят на рассмотрение **{interaction.user.mention}**!",
            ephemeral=True
        )
        # Публичное подтверждение в самом тикете, видимое заявителю
        await ticket_channel.send(
            f"📋 Тикет взят на рассмотрение модератором **{interaction.user.name}**."
        )

        # Уведомляем автора заявки в ЛС
        creator_id = get_creator_id_from_topic(ticket_channel)
        embed = discord.Embed(
            title="📋 Ваша заявка взята на рассмотрение",
            description=f"Модератор **{interaction.user.name}** начал рассматривать вашу заявку.",
            color=0x5865F2
        )
        embed.set_footer(text="Семья Хейтер | GTA 5 RP")

        async def report(text):
            await ticket_channel.send(text)

        await send_dm_with_feedback(
            interaction.client, interaction.guild,
            creator_id, embed, "взятие на рассмотрение", report
        )

    @discord.ui.button(label="🔄 Сняться с рассмотрения", style=discord.ButtonStyle.secondary, custom_id="untake_ticket")
    async def untake_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not has_allowed_role(interaction):
            await interaction.followup.send("❌ У тебя нет прав сниматься с рассмотрения!", ephemeral=True)
            return

        ticket_channel = get_ticket_channel(interaction)
        current_name = ticket_channel.name

        if not current_name.startswith("рассматривает-"):
            await interaction.followup.send("❌ Этот тикет сейчас не рассматривается!", ephemeral=True)
            return

        creator_id = get_creator_id_from_topic(ticket_channel)
        if not creator_id:
            await interaction.followup.send("❌ Не удалось определить создателя тикета.", ephemeral=True)
            return

        new_name = f"тикет-{creator_id}"
        try:
            await ticket_channel.edit(name=new_name)
        except discord.NotFound:
            await interaction.followup.send("❌ Канал уже не существует.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send("❌ Не удалось переименовать канал.", ephemeral=True)
            print(f"Ошибка переименования: {e}")
            return

        await interaction.followup.send(
            f"✅ Ты снялся с рассмотрения тикета **{current_name}**.",
            ephemeral=True
        )
        await ticket_channel.send(f"🔄 **{interaction.user.name}** снялся с рассмотрения тикета.")


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
                        # manage_threads нужен, чтобы персонал автоматически видел приватный
                        # тред с кнопками управления тикетом, а заявитель — нет
                        await category.set_permissions(role, read_messages=True, connect=True, manage_threads=True)

            new_channel = await guild.create_text_channel(
                f'тикет-{message.author.name}',
                category=category
            )

            # Сохраняем ID РЕАЛЬНОГО заявителя (найденного по нику в тексте заявки),
            # а НЕ message.author.id — потому что заявки чаще всего публикует вебхук/бот-интеграция
            # с сайта, а не сам заявитель, и у вебхука нет настоящего Discord-аккаунта для DM.
            if user:
                await new_channel.edit(topic=f"Создатель: {user.id}")
            else:
                await new_channel.edit(topic="Создатель: не найден")
                print(f"⚠️ Не удалось сопоставить заявителя с участником сервера. "
                      f"Искали по: '{discord_username}'. Автор сообщения в канале: {message.author} ({message.author.id})")

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

            # Панель с кнопками управления кладём в ПРИВАТНЫЙ тред,
            # чтобы заявитель их вообще не видел — видно только персоналу
            # (у ролей из ALLOWED_ROLES есть manage_threads, поэтому тред виден им автоматически)
            try:
                panel_thread = await new_channel.create_thread(
                    name="🔒 Панель управления",
                    type=discord.ChannelType.private_thread,
                    invitable=False,
                    reason="Приватная панель кнопок управления тикетом"
                )
                await panel_thread.send("🔽 **Действия с тикетом:**", view=view)
            except Exception as e:
                # Если по какой-то причине приватный тред создать не вышло (например, не хватает прав) —
                # не ломаем создание тикета, а кладём кнопки прямо в канал, как раньше
                print(f"⚠️ Не удалось создать приватный тред для панели кнопок: {e}")
                await new_channel.send("🔽 **Действия с тикетом:**", view=view)

            await new_channel.set_permissions(guild.default_role, read_messages=False)

            if user:
                await new_channel.set_permissions(user, read_messages=True, send_messages=True)

            for role_id in ALLOWED_ROLES:
                role = guild.get_role(role_id)
                if role:
                    # manage_threads даёт возможность видеть приватный тред с кнопками
                    await new_channel.set_permissions(role, read_messages=True, send_messages=True, manage_threads=True)

            admin_role = discord.utils.get(guild.roles, name='Admin')
            if admin_role:
                await new_channel.set_permissions(admin_role, read_messages=True, send_messages=True, manage_threads=True)


client = MyClient(intents=discord.Intents.all())
client.run(TOKEN)
