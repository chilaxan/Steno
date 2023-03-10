import discord
from dotenv import load_dotenv
import os
import asyncio
import requests
import wave
import io
import time

bot = discord.Bot()
halt = False
session = None

from discord.sinks import WaveSink, Filters, AudioData

class SumWaveSink(WaveSink):
    @Filters.container
    def write(self, data, user):
        if not hasattr(self, 'file'):
            self.file = AudioData(io.BytesIO())
        self.file.write(data)

def post(vc, session, update, summarize, title, page=0):
    async def inner(sink, channel, *args):
        nonlocal update, page
        sink.file.cleanup()
        sink.format_audio(sink.file)
        resp = requests.post(
            f'http://localhost:3333/transcribe/{session}',
            data={'summarize': summarize},
            files={'clip': sink.file.file}
        )
        em = discord.Embed(title = title, color = 
        discord.Color.green())
        text = resp.json()['output'][701 * page: 701 * (page + 1)]
        em.add_field(name = 'Content', value = text)
        if len(text) > 700:
            page += 1
            update = await channel.send(embed=em)
        else:
            await update.edit(embed=em)
        if not halt:
            vc.start_recording(
                SumWaveSink(filters={'time':15}),
                post(vc, session, update, summarize, title, page),
                channel
            )
    return inner

@bot.command(description="Start Transcribing")
async def start(ctx, summarize: bool, title: str="Summary"):
    global halt, session
    voice = ctx.author.voice

    if not voice:
        return await ctx.respond("You aren't in a voice channel!")
    vc = await voice.channel.connect()
    halt = False

    em = discord.Embed(title = title, color = discord.Color.green())
    em.add_field(name = '', value = '<None>')
    update = await ctx.send(embed=em)

    session = requests.get('http://localhost:3333/session').json()['session_id']

    vc.start_recording(
        SumWaveSink(filters={'time':10}),
        post(vc, session, update, summarize, title),
        ctx.channel
    )
    await ctx.respond('Started Transcribing')

@bot.command(description="Stop Current Transcription Session")
async def stop(ctx):
    global halt
    halt = True
    requests.delete(f'http://localhost:3333/delete/{session}')
    await ctx.guild.voice_client.disconnect()
    await ctx.respond("Stopped Transcribing")

load_dotenv()
bot.run(os.getenv('DISCORD_BOT_TOKEN'))