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

    words = {}  # dict of serverid : (word, timeofr, user, timeofs) (klaxon word, time since said and not reset, user waiting on reset, time since set)
    serverinfo = {}  # dict of serverid : [prefix, ignored, optedout, resetd] [bot command prefix, ingored channels, opted out users, days before reset]
    
    # sql presets
    create_words_table = """CREATE TABLE IF NOT EXISTS words (
        server_id INTEGER PRIMARY KEY,
        word TEXT DEFAULT 'klaxon',
        timeofr INTEGER DEFAULT 0 NOT NULL,
        user INTEGER DEFAULT NULL,
        timeofs INTEGER DEFAULT 0 NOT NULL
    );"""
    insert_words_table = """INSERT INTO words(server_id, word, timeofr, user, timeofs)
        VALUES(?,?,?,?,?)
    """
    update_words_table = 'UPDATE words SET word = ?, timeofr = ?, user = ?, timeofs = ? WHERE server_id = ?'
    find_words_table = 'SELECT * FROM words WHERE server_id = ?'
    
    create_serverinfo_table = """CREATE TABLE IF NOT EXISTS serverinfo (
        server_id INTEGER PRIMARY KEY,
        prefix TEXT DEFAULT 'k!' NOT NULL,
        ignored TEXT DEFAULT NULL,
        optedout TEXT DEFAULT NULL,
        resetd INTEGER DEFAULT 30
    );"""
    insert_serverinfo_table = """INSERT INTO serverinfo(server_id, prefix, ignored, optedout, resetd)
        VALUES(?,?,?,?,?)
    """
    # update_serverinfo_table = 'UPDATE serverinfo SET prefix = ?, ignored = ?, optedout = ? WHERE server_id = ?'
    find_serverinfo_table = 'SELECT * FROM serverinfo WHERE server_id = ?'
    

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print("Klaxon Bot v1.1")
        # creates a SQLite 3 database if you don't have one
        try:
            with sqlite3.connect("serverwords.db") as conn:
                print(f"Opened SQLite database with version {sqlite3.sqlite_version} successfully.")
                cursor = conn.cursor()
                cursor.execute(self.create_words_table)
                cursor.execute(self.create_serverinfo_table)
                conn.commit()
        except sqlite3.OperationalError as e:
            print("Failed to open database:", e)
            
        print('------')

    async def on_message(self, message):
        
        # does nothing if bots say it
        if message.author.bot:
            return
        
        # id of the server it is said in
        serverid = message.guild.id if (type(message.channel) is not discord.channel.DMChannel) else None
        
        # user dm understander
        if (type(message.channel) is discord.channel.DMChannel):
            userlist = list(tpl[2] for tpl in self.words.values())  # gets a list of all stored users who need to reset
            if (message.author.id in userlist):
                tempword = message.content.lower().strip()
                if tempword.isalpha():
                    if (userlist.count(message.author.id) > 1):
                        await message.author.send("You've managed to trigger the Klaxon in multiple servers. For this unprecedented level of stupidity, your word will apply to all relevant servers.")
                    for servid, wordinfo in self.words.items():  # for loop through all of the set words allows for someone to set multiple if triggered by same person
                        if (message.author.id == wordinfo[2]):
                            self.words[servid] = (tempword, 0, None, time.time())
                            with sqlite3.connect("serverwords.db") as conn:
                                cursor = conn.cursor()
                                cursor.execute(self.update_words_table, (tempword, 0, None, time.time(), servid))
                    await message.author.send("You have selected \'{0}\' as the new Klaxon word.".format(tempword))
                else:  # if it has non-alpha characters like numbers or spaces
                    await message.author.send("I said word. \'{0}\' isn't a word. Idiot.".format(tempword))
            print("DM from " + str(message.author.display_name))
            return
        
        # if not currently in dictionary of servers (like on bot reset), check if in sql, add if so, make new entry if not
        if serverid not in self.words:
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.find_words_table, (serverid,))
                exists = cursor.fetchone()
                if exists:
                    if len(exists) != 5:  # hard coded in for every breaking update that changes db entry formnat to make previous db entries backwards compatible
                        cursor.execute('ALTER TABLE words ADD COLUMN timeofs INTEGER DEFAULT 0 NOT NULL')
                        cursor.execute('UPDATE words SET timeofs = ? WHERE server_id = ?', (time.time(), serverid))
                        cursor.execute(self.find_words_table, (serverid,))
                        exists = cursor.fetchone()
                    self.words[serverid] = exists[1:]
                else:
                    cursor.execute(self.insert_words_table, (serverid, "klaxon", 0, None, time.time()))
                    self.words[serverid] = ("klaxon", 0, None, time.time())

        # same as above but with serverinfo
        if serverid not in self.serverinfo:
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.find_serverinfo_table, (serverid,))
                exists = cursor.fetchone()
                if exists:
                    if len(exists) != 5:  # hard coded in for every breaking update that changes db entry formnat to make previous db entries backwards compatible
                        cursor.execute('ALTER TABLE serverinfo ADD COLUMN resetd INTEGER DEFAULT 30 NOT NULL')
                        cursor.execute(self.find_words_table, (serverid,))
                        exists = cursor.fetchone()
                    self.serverinfo[serverid] = list(exists[1:])
                else:
                    cursor.execute(self.insert_serverinfo_table, (serverid, "k!", None, None, 30))
                    self.serverinfo[serverid] = ["k!", "", "", 30]
                    
        print(self.words[serverid])  # testing
                    
        # if been 24h since said and not reset
        if (self.words[serverid][1] > 0) and (time.time() >= self.words[serverid][1] + 86400):  # 86400 is 24h
            await self.get_user(self.words[serverid][2]).send("I haven't heard from you in 24 hours, resetting the word to \"klaxon\".")
            self.words[serverid] = ("klaxon", 0, None, time.time())
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.update_words_table, ("klaxon", 0, None, time.time(), serverid))
            # self.generate_klaxon_mp4(self.words[serverid][0].upper()) # generate video
        
        # if been 30d since said and not triggered
        if (self.words[serverid][3] > 0) and (time.time() >= self.words[serverid][3] + (86400 * self.serverinfo[serverid][3])):  # 86400 is 1d
            self.words[serverid] = ("klaxon", 0, None, time.time())
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.update_words_table, ("klaxon", 0, None, time.time(), serverid))
        
        # if command (starts with prefix)
        if message.content.startswith(self.serverinfo[serverid][0]):
            command = message.content.removeprefix(self.serverinfo[serverid][0])  # remove prefix to check command
            
            if command.startswith("help"):
                await message.channel.send( \
                    "**{0}prefix `s`** - Changes the current prefix for commands to `s` (default is k!).\n" \
                    "**{0}ignore** - Toggles whether future messages in the current channel can trigger the Klaxon.\n" \
                    "**{0}optout** - Toggles whether the command's author can trigger the Klaxon.\n" \
                    "**{0}timer** - Sets how long, in days, before an untriggered word is reset to 'klaxon' (default is 30 days)".format(self.serverinfo[serverid][0]))
            
            if command.startswith("prefix "):  # updates prefix
                newpre = command.removeprefix("prefix ")
                self.serverinfo[serverid][0] = newpre
                with sqlite3.connect("serverwords.db") as conn:  # update db after ignore/unignore
                        cursor = conn.cursor()
                        cursor.execute('UPDATE serverinfo SET prefix = ? WHERE server_id = ?', (newpre, serverid))
                await message.channel.send("The new prefix for this server is `{0}`.".format(newpre))
            
            if command.startswith("ignore"):  # ignores channels
                ign = self.serverinfo[serverid][1]
                if not ign:  # if list is empty
                    self.serverinfo[serverid][1] = str(message.channel.id)
                    await message.channel.send("<#{0}> ignored.".format(message.channel.id))
                elif str(message.channel.id) in ign:
                    self.serverinfo[serverid][1] = ign.replace(str(message.channel.id), "").replace(",,", ",").strip(",")  # removes from string then clears errant commas
                    await message.channel.send("<#{0}> unignored.".format(message.channel.id))
                else:
                    self.serverinfo[serverid][1] += "," + str(message.channel.id)
                    await message.channel.send("<#{0}> ignored.".format(message.channel.id))
                with sqlite3.connect("serverwords.db") as conn:  # update db after ignore/unignore
                        cursor = conn.cursor()
                        cursor.execute('UPDATE serverinfo SET ignored = ? WHERE server_id = ?', (self.serverinfo[serverid][1], serverid))
              
            if command.startswith("optout"):  # opts out users
                opt = self.serverinfo[serverid][2]
                if not opt:  # if list is empty
                    self.serverinfo[serverid][2] = str(message.author.id)
                    await message.channel.send("You have opted-out of being klaxoned.")
                elif str(message.author.id) in opt:
                    self.serverinfo[serverid][2] = opt.replace(str(message.author.id), "").replace(",,", ",").strip(",")  # removes from string then clears errant commas
                    await message.channel.send("You have opted-in to being klaxoned.")
                else:
                    self.serverinfo[serverid][2] += "," + str(message.author.id)
                    await message.channel.send("You have opted-out of being klaxoned.")
                with sqlite3.connect("serverwords.db") as conn:  # update db after ignore/unignore
                        cursor = conn.cursor()
                        cursor.execute('UPDATE serverinfo SET optedout = ? WHERE server_id = ?', (self.serverinfo[serverid][2], serverid))
                        
            if command.startswith("timer "):  # sets time in days before reset
                days = command.removeprefix("timer ")
                if not days.isnumeric():
                    await message.channel.send("Hey buddy, did you just blow in from stupid town? That's not a number.")
                elif days == "0":
                    await message.channel.send("I bet you think you're real funny.")
                else:
                    self.serverinfo[serverid][3] = int(days)
                    await message.channel.send("The Klaxon will now reset after {0} days.".format(days))
                    with sqlite3.connect("serverwords.db") as conn:  # update db after ignore/unignore
                        cursor = conn.cursor()
                        cursor.execute('UPDATE serverinfo SET resetd = ? WHERE server_id = ?', (self.serverinfo[serverid][3], serverid))
                    
                        
            print(self.serverinfo[serverid])
        
        # do not listen to ignored channels (except ignore command)
        if self.serverinfo[serverid][1] and (str(message.channel.id) in self.serverinfo[serverid][1]):
            return
        
        # ignore opted-out users
        if self.serverinfo[serverid][2] and (str(message.author.id) in self.serverinfo[serverid][2]):
            return

        # klaxon word finder
        if self.words[serverid][0] and (self.check_in_message(message.content, self.words[serverid][0])):
            wordsaid = self.words[serverid][0]
            self.words[serverid] = (None, time.time(), message.author.id, 0)
            with sqlite3.connect("serverwords.db") as conn:
                cursor = conn.cursor()
                cursor.execute(self.update_words_table, (None, time.time(), message.author.id, 0, serverid))
            await message.channel.typing() # posts klaxon bot is typing... while generating video
            self.generate_klaxon_mp4(wordsaid.upper()) # generate video          
            if self.words[serverid][0] == "test":
                await message.channel.send("# :camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(wordsaid, message.author.id), file=discord.File("klaxon_test.mp4", filename="klaxon.mp4"))
            else:
                await message.channel.send("# :camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(wordsaid, message.author.id), file=discord.File("klaxon.mp4", filename="klaxon.mp4"))
            await message.author.send("Please respond with a new Klaxon word. Choose wisely.")
            print("{0} said by {1} in {2}".format(message.content, message.author.name, message.channel.name))
            return
    
    # checks if word is in the message, not as a substring
    @staticmethod
    def check_in_message(mess, word):
        translator = str.maketrans(string.punctuation, ' '*len(string.punctuation))  # map punctuation to space (based)
        return word in mess.lower().translate(translator).split()

    # make mp4 file
    def generate_klaxon_mp4(self, klaxon_word):
        def text2png(text):
            width, height = 1418, 1072
            max_width = width - 40  # margin
            default_font_size = 200
            min_font_size = 30 # minimum font size, no multiline text yet...
            
            font_path = "FranklinGothic.ttf" if text.isascii() else "UKIJCJK.ttf"
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
