import discord
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

with open('config.json') as f:
    data = json.load(f)
    token = data["TOKEN"]

# on message, parses
class MyClient(discord.Client):

    word = "test"
    usr = None
    ignored = []

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message):

        # does nothing if bots say it
        if message.author == self.user:
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
        
        # do not listen to ignored channels (except ignore command)
        if message.channel.id in self.ignored:
            return

        # klaxon word finder
        if self.word and (self.word in message.content.lower()):
            self.usr = message.author
            
            if self.word == "test":
                await message.channel.send("# :camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(self.word, message.author.id), file=discord.File("klaxon_test.mp4", filename="klaxon.mp4"))
            else:
                await message.channel.send("# :camera_with_flash: The Klaxon word \'{0}\' was said by <@{1}> and earned them -10 points! :camera_with_flash:".format(self.word, message.author.id), file=discord.File("klaxon.mp4", filename="klaxon.mp4"))

            self.word = None
            await message.author.send("Please respond with a new Klaxon word. Choose wisely.")
            print("{0} said by {1} in {2}".format(message.content, message.author.name, message.channel.name))
            return
    
        # user dm understander
        if (type(message.channel) is discord.channel.DMChannel) and self.usr and (self.usr == message.author):
            tempword = message.content.lower().strip()
            if tempword.isalpha():
                self.word = tempword
                await message.author.send("Setting word...")
                self.generate_klaxon_mp4(self.word.upper()) # generate video
                await message.author.send("You have selected \'{0}\' as the new Klaxon word.".format(self.word))
            else:
                await message.author.send("I said word. \'{0}\' isn't a word. Idiot.".format(tempword))
            return
        

    # make mp4 file

    def generate_klaxon_mp4(self, klaxon_word):
        def text2png(text):
            width, height = 1417, 1072
            max_width = width - 40  # margin
            default_font_size = 200
            min_font_size = 30 # minimum font size, no multiline text yet...

            font_path = "FranklinGothic.ttf"
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
