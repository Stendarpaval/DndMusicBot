#!/usr/bin/env python3

import os
import subprocess
import sys
import pandas as pd
import asyncio
import random
from botsettings import Settings

import discord
from discord.ext import commands

print("Python version:",sys.version)

# Logging:

import logging

currentdir = os.path.dirname(os.path.abspath(__file__)) + '/'

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename=currentdir + 'discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)



# Obtain settings from BotSettings.py
bot_settings = Settings()
command_prefixes = bot_settings.command_prefixes
extension_folder = bot_settings.extension_folder
TOKEN = bot_settings.TOKEN
owner_id = bot_settings.owner_id
text_channel_id = bot_settings.text_channel_id

def is_me(m):
    """Check if message was sent by the client/bot."""
    return m.author == client.user

def is_author(m):
    """Check if message was sent by the bot's owner."""
    user_id = owner_id
    author = client.get_user(user_id)
    return m.author == author

def is_presentator(m):
    """Checks if message was sent by DSB presentator"""
    owner = client.get_user(owner_id)
    maarten = client.get_user(135157492987592705)
    return (m.author == owner or m.author == maarten)


# connect to bot
print('Connecting to bot...')
client = commands.Bot(command_prefix=command_prefixes, description='Relatively simple music bot')

client.remove_command('help')

text_channel = client.get_channel(text_channel_id)

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.command()
async def ping(channel=text_channel):
    """Replies with Pong! (and latency)"""

    pongmsg = await channel.send(f'Pong! {round(client.latency  * 1000)}ms')
    await discord.Message.delete(pongmsg, delay=10)


@client.listen()
async def on_message(message):
    """Replies when someone mentions the bot."""
    reply_options = [   'Hi there, {0.author.mention}. Did you need me for something?'.format(message),
                        'Hello, {0.author.mention}!'.format(message),
                        'Sup, {0.author.mention}?'.format(message),
                        "Hmm? Did someone mention me?".format(message),
                        "Hey, {0.author.mention}! Anything I can do to help?".format(message)]
    if message.author == client.user:
        return
    else:
        mention_name = '<@!' + client.user.mention[2:]
        if mention_name in message.content.split():
            async with message.channel.typing():
                await asyncio.sleep(random.choice(range(1,3)))
                await message.channel.send(random.choice(reply_options))


@client.command(aliases=['d'])
@commands.is_owner()
async def delete(channel=text_channel):
    """Delete previous 100 messages of this bot. Alias: <d>"""
    deleted = await channel.channel.purge(limit=100, check=is_me)
    delmsg = await channel.channel.send('Deleted my last {} message(s)'.format(len(deleted)))
    await discord.Message.delete(delmsg, delay=10)


@client.command(aliases=['dm'])
@commands.is_owner()
async def delete_my_messages(channel=text_channel, *, msgnum: int =5):
    """Deletes previous 5 messages of the bot's owner."""
    deleted = await channel.channel.purge(limit=msgnum, check=is_author)


@client.command(aliases=['dd'])
@commands.is_owner()
async def delete_last_messages(channel=text_channel, *, msgnum: int =5):
    """Deletes previous 5 messages of this bot."""
    deleted = await channel.channel.purge(limit=msgnum, check=is_me)


@client.command(aliases=['l'])
async def load(ctx, extension):
    """Loads extension. Alias: <l>"""
    client.load_extension(f'extensions.{extension}')


@client.command(aliases=['ul'])
async def unload(ctx, extension):
    """Unloads extension. Alias: <ul>"""
    client.unload_extension(f'extensions.{extension}')


@client.command(aliases=['r'])
@commands.is_owner()
async def reload_ext(channel=text_channel, extension='all'):
    """Reloads extension(s). Alias: <r>"""
    if extension == 'all':
        for filename in os.listdir(extension_folder):
            if filename.endswith('.py'):
                client.unload_extension(f'extensions.{filename[:-3]}')
                client.load_extension(f'extensions.{filename[:-3]}')
        reloadmsg = await channel.send('Reloaded all extensions.')
        await discord.Message.delete(reloadmsg, delay=10)
    else:
        client.unload_extension(f'extensions.{extension}')
        client.load_extension(f'extensions.{extension}')
        print('Extension {} reloaded.'.format(extension))
        reloadmsg = await channel.send('Reloaded.')
        await discord.Message.delete(reloadmsg, delay=10)


# Load all extensions when starting up the bot.
for filename in os.listdir(extension_folder):
    if filename.endswith('.py'):
        client.load_extension(f'extensions.{filename[:-3]}')


@client.command()
@commands.is_owner()
async def shutdown(channel=text_channel):
    """Shutdown the music bot."""
    print("Disconnecting from Discord...")
    shutdownmsg = await channel.send("I'm shutting down. See ya!")
    await discord.Message.delete(shutdownmsg, delay=10)
    try:
        await client.wait_until_ready()
        await client.logout()
        await asyncio.sleep(3.0)
        print('Successfully disconnected from Discord. Shutting down. Bye~!')
    except discord.ConnectionClosed:
        print("Connection closed.")
        pass
    except discord.ClientException:
        print("Something went wrong with the client.")
        pass
    except asyncio.CancelledError:
        # This is usually what happens when shutting down successfully.
        # Not entirely sure why. But it seems to work quite well.
        print("Something successfully cancelled. It's probably fine.")
        pass
    except Exception as ex:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(ex).__name__, ex.args)
        print(message)
        pass
    finally:
        os._exit(0)


@ping.after_invoke
@delete_my_messages.after_invoke
@delete.after_invoke
@delete_last_messages.after_invoke
@load.after_invoke
@unload.after_invoke
@reload_ext.after_invoke
@shutdown.after_invoke
async def remove_command_msg(channel=text_channel):
        """Removes the messages of users after invoking the 
        requested command."""
        print("Deleting user command...")
        await discord.Message.delete(channel.message, delay=1)


client.run(TOKEN)
