import discord
import os

TOKEN = os.environ['TOKEN']
CHANNEL_NAME = 'заявки-бот'

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'✅ Бот {self.user} запущен!')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.channel.name == CHANNEL_NAME:
            guild = message.guild
            new_channel = await guild.create_text_channel(f'тикет-{message.author.name}')
            await new_channel.send(f'📩 **Новая заявка от {message.author.mention}!**')
            await new_channel.send(message.content)
            admin_role = discord.utils.get(guild.roles, name='Admin')
            if admin_role:
                await new_channel.set_permissions(admin_role, read_messages=True, send_messages=True)
            await new_channel.set_permissions(guild.default_role, read_messages=False)

client = MyClient(intents=discord.Intents.all())
client.run(TOKEN)