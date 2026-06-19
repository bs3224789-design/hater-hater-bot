import discord
import os
import re

TOKEN = os.environ['TOKEN']
CHANNEL_NAME = 'заявки-бот'

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
                    # Проверяем разные варианты: имя, имя#тег, частичное совпадение
                    if (member.name.lower() == discord_nick.lower() or 
                        str(member).lower() == discord_nick.lower() or
                        discord_nick.lower() in member.name.lower()):
                        user = member
                        break

            guild = message.guild
            new_channel = await guild.create_text_channel(f'тикет-{message.author.name}')

            mention = user.mention if user else discord_nick or 'Не указан'

            await new_channel.send(f'📩 **Новая заявка от {mention}!**')
            await new_channel.send(content)

            if user:
                await new_channel.set_permissions(user, read_messages=True, send_messages=True)
            
            admin_role = discord.utils.get(guild.roles, name='Admin')
            if admin_role:
                await new_channel.set_permissions(admin_role, read_messages=True, send_messages=True)
            
            await new_channel.set_permissions(guild.default_role, read_messages=False)

client = MyClient(intents=discord.Intents.all())
client.run(TOKEN)
