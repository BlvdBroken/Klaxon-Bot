import discord
import json
import time
import cv2
import string
import numpy as np
import sqlite3
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

with open('config.json') as f:
    data = json.load(f)
    token = data["TOKEN"]

# on message, parses
class MyClient(discord.Client):

    words = {} # dict of serverid : (word, timeof, user) with timeof being time since said and not reset and user being id of last user said
    ignored = [] # ignored channels
    optedout = [] # opted out users
    timeof = 0  # time since said and not reset
    
    # sql presets
    create_table = """CREATE TABLE IF NOT EXISTS words (
        server_id INTEGER PRIMARY KEY,
        word TEXT DEFAULT 'klaxon',
        timeof INTEGER DEFAULT 0 NOT NULL,
        user INTEGER DEFAULT NULL
    );"""
    insert_table = """INSERT INTO words(server_id, word, timeof, user)
        VALUES(?,?,?,?)
    """
    update_table = 'UPDATE words SET word = ?, timeof = ?, user = ? WHERE server_id = ?'
    find_table = 'SELECT * FROM words WHERE server_id = ?'

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print("Klaxon Bot v1.0")
        # creates a SQLite 3 database if you don't have one
        try:
            with sqlite3.connect("serverwords.db") as conn:
                print(f"Opened SQLite database with version {sqlite3.sqlite_version} successfully.")
                cursor = conn.cursor()
                cursor.execute(self.create_table)
                conn.commit()
        except sqlite3.OperationalError as e:
            print("Failed to open database:", e)
            
        print('------')

    async def on_message(self, message):
        
        # id of the server it is said in
        serverid = message.guild.id if (type(message.channel) is not discord.channel.DMChannel) else None
        
        # if not currently in dictionary of servers (like on bot reset), check if in sql, add if so, make new entry if not
        if serverid and serverid not in self.words:
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.find_table, (serverid,))
                exists = cursor.fetchone()
                if exists:
                    self.words[serverid] = exists[1:]
                else:
                    cursor.execute(self.insert_table, (serverid, "klaxon", 0, None))
                    self.words[serverid] = ("klaxon", 0, None)
                    
        print((self.words[serverid]) if serverid else ("DM from " + message.author.display_name))
                    
        # if been 24h since said and not reset
        if serverid and (self.words[serverid][1] > 0) and (time.time() >= self.words[serverid][1] + 86400): # 86400 is 24h
            await self.get_user(self.words[serverid][2]).send("I haven't heard from you in 24 hours, resetting the word to \"klaxon\"")
            self.words[serverid] = ("klaxon", 0, None)
            self.generate_klaxon_mp4(self.words[serverid][0].upper()) # generate video
            return

        # does nothing if bots say it
        if message.author.bot:
            return
                
        # ignore channels
        if message.content.startswith("k!ignore"):
            if message.channel.id in self.ignored:
                self.ignored.remove(message.channel.id)
                await message.channel.send("<#{0}> unignored.".format(message.channel.id))
            else:
                self.ignored.append(message.channel.id)
                await message.channel.send("<#{0}> ignored.".format(message.channel.id))
            return
        
        # allow opt-out of users
        if message.content.startswith("k!optout"):
            if message.author in self.optedout:
                self.optedout.remove(message.author)
                await message.channel.send("You have opted-in to being klaxoned.")
            else:
                self.optedout.append(message.author)
                await message.channel.send("You have opted-out of being klaxoned.")
            return
        
        # do not listen to ignored channels (except ignore command)
        if message.channel.id in self.ignored:
            return
        
        # ignore opted-out users
        if message.author in self.optedout:
            return

        # klaxon word finder
        if serverid and self.words[serverid][0] and (self.check_in_message(message.content, self.words[serverid][0])):
            wordsaid = self.words[serverid][0]
            self.words[serverid] = (None, time.time(), message.author.id)
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.update_table, (None, time.time(), message.author.id, serverid))
            await message.channel.typing() # posts klaxon bot is typing... while generating video
            self.generate_klaxon_mp4(wordsaid.upper()) # generate video          
            if self.words[serverid][0] == "test":
                await message.channel.send("# :camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(wordsaid, message.author.id), file=discord.File("klaxon_test.mp4", filename="klaxon.mp4"))
            else:
                await message.channel.send("# :camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(wordsaid, message.author.id), file=discord.File("klaxon.mp4", filename="klaxon.mp4"))
            await message.author.send("Please respond with a new Klaxon word. Choose wisely.")
            print("{0} said by {1} in {2}".format(message.content, message.author.name, message.channel.name))
            return
    
        # user dm understander
        if (type(message.channel) is discord.channel.DMChannel):
            userlist = list(tpl[2] for tpl in self.words.values())
            if (message.author.id in userlist):
                tempword = message.content.lower().strip()
                if tempword.isalpha():
                    if (userlist.count(message.author.id) > 1):
                        await message.author.send("You've managed to trigger the Klaxon in multiple servers. For this unprecedented level of stupidity, your word will apply to all relevant servers.")
                    for servid, wordinfo in self.words.items():
                        if (message.author.id == wordinfo[2]):
                            self.words[servid] = (tempword, 0, None)
                            with sqlite3.connect("serverwords.db") as conn:
                                cursor = conn.cursor()
                                cursor.execute(self.update_table, (tempword, 0, None, servid))
                    await message.author.send("You have selected \'{0}\' as the new Klaxon word.".format(tempword))
                else:
                    await message.author.send("I said word. \'{0}\' isn't a word. Idiot.".format(tempword))
            return
    
    # checks if word is in the message, not as a substring
    @staticmethod
    def check_in_message(mess, word):
        translator = str.maketrans(string.punctuation, ' '*len(string.punctuation)) # map punctuation to space (based)
        return word in mess.lower().translate(translator).split()

    # make mp4 file
    def generate_klaxon_mp4(self, klaxon_word):
        def text2png(text):
            width, height = 1418, 1072
            max_width = width - 40  # margin
            default_font_size = 200
            min_font_size = 30 # minimum font size, no multiline text yet...

            font_path = "FranklinGothic.ttf"
            if (re.match("^[ABCDEFGHIJKLMNOPQRSTUVWXYZ]*$", text) == False):
                font_path = "FreeSansBold.otf"
            font_size = default_font_size
            font = ImageFont.truetype(font_path, font_size)

            image = Image.new('RGB', (width, height), color='black')
            draw = ImageDraw.Draw(image)

            # dynamic sizing
            text_width = draw.textlength(text, font=font)
            while text_width > max_width and font_size > min_font_size:
                font_size -= 10  
                font = ImageFont.truetype(font_path, font_size)
                text_width = draw.textlength(text, font=font)

            # centering
            text_height = font_size
            position = ((width - text_width) // 2, (height - text_height) // 2)

            draw.text(position, text, font=font, fill="white")

            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR) # convert back to opencv LOL

        fps = 30
        loop_duration = 0.5 # seconds
        bitrate = "1024k"
        codec = "libx264"
        audio_bitrate = "128k"
        output_file = "klaxon.mp4"

        klaxon_on, klaxon_off = text2png(klaxon_word), text2png("")
        clips=[]

        for _ in range(5):
            clips.append(ImageClip(klaxon_on).set_duration(loop_duration))
            clips.append(ImageClip(klaxon_off).set_duration(loop_duration))
        clips.append(ImageClip(klaxon_on).set_duration(loop_duration))

        video = concatenate_videoclips(clips, method="compose")

        audio_file = "klaxon.ogg"
        audio = AudioFileClip(audio_file).subclip(0, video.duration)
        video = video.set_audio(audio)

        video.write_videofile(output_file, fps=fps, codec=codec, bitrate=bitrate, audio_bitrate=audio_bitrate)



        


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = MyClient(intents=intents)
client.run(token)
