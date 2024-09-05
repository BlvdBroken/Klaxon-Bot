import discord
import json

with open('config.json') as f:
    data = json.load(f)
    token = data["TOKEN"]

# on message, parses
class MyClient(discord.Client):

    word = "test"
    usr = None

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message):

        # does nothing if bots say it
        if message.author == self.user:
            return

        # klaxon word finder
        if self.word and (self.word in message.content.lower()):
            self.usr = message.author
            await message.channel.send(":camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(self.word, message.author.id))
            self.word = None
            await message.author.send("Please respond with a new Klaxon word. Choose wisely.")
            return
    
        # user dm understander
        if (type(message.channel) is discord.channel.DMChannel) and self.usr and (self.usr == message.author):
            tempword = message.content.lower().strip()
            if tempword.isalpha():
                self.word = tempword
                await message.author.send("You have selected \'{0}\' as the new Klaxon word.".format(self.word))
                self.usr = None
            else:
                await message.author.send("I said word. \'{0}\' isn't a word. Idiot.".format(tempword))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = MyClient(intents=intents)
client.run(token)
