import os
import sys
import subprocess
import shutil
import shlex
import re
import time
import math
import pandas as pd
from random import choice
from random import shuffle
from subprocess import call

import asyncio
import discord
from discord.ext import tasks, commands

# Import settings from botsettings.py in parent folder:
from os.path import dirname, abspath
d = dirname(dirname(abspath(__file__)))
sys.path.append(d)
from botsettings import Settings

bot_settings = Settings()
localmusicpath_prefix = bot_settings.localmusicpath_prefix
filetype_extensions = bot_settings.filetype_extensions
global voice_channel_id
voice_channel_id = bot_settings.voice_channel_id

global dont_delete
dont_delete = False
text_channel = 0

def fetch_playlists():
    '''Look up folders in music directory and use their names for 
    playlist names.'''
    plist_names = next(os.walk(localmusicpath_prefix))[1]
    if plist_names == None:
        print("Warning: No music folders found for playlists.")
    return plist_names
plist_names = fetch_playlists()


def yt_dl(yt_url):
    '''Downloads a youtube song.'''
    cmnd = ['youtube-dl' ,yt_url, '-x', '--no-playlist']
    p = subprocess.Popen(cmnd, cwd=bot_settings.localmusicpath_prefix + 'yt', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    output = str(out)
    index_start = output.find('[ffmpeg] Destination: ')
    index_end = output.find("Deleting original file")
    print("index_start:", index_start)
    print("index_end:", index_end)
    if index_start == -1 and index_end == -1:
        return "error", False
    songname = output[(index_start+22):(index_end-2)]
    cmnd = ['youtube-dl', '--rm-cache-dir']
    p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for ext in filetype_extensions:
        if songname.endswith(ext):
            ext_length = len(ext)
            extension = ext
            break
    new_songname = songname[:-(12+ext_length)] + extension
    os.rename(bot_settings.localmusicpath_prefix + 'yt/' + songname, bot_settings.localmusicpath_prefix + 'yt/' + new_songname)
    return new_songname, True


# Define general functions:
def probe_file(filename):
    '''Determine song duration.'''
    cmnd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', filename]
    p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err =  p.communicate()
    output = str(out)
    duration_float = float(output[2:-3])

    if err:
        print("error:")
        print(err)
    else:
        return duration_float


def make_playlist(name: str):
    """Make a new playlist."""
    if name == 'other':
        f = open(localmusicpath_prefix + name + '_playlist.txt','w')
    else:
        f = open(localmusicpath_prefix + name + '/' + name + '_playlist.txt','w')

    f.close()


def add_to_playlist(name: str, song: str):
    """Add a song to an existing playlist."""
    if name == 'other':
        f = open(localmusicpath_prefix + name + '_playlist.txt','a')
    else:
        f = open(localmusicpath_prefix + name + '/' + name + '_playlist.txt','a')
    if song is not None:
        f.write(song + '\n')
    f.close()


def read_playlist(name):
    """Read songs in playlist."""
    try:
        if name == 'other':
            playlist_data = pd.read_csv(localmusicpath_prefix + name + '_playlist.txt', 
                                        sep='\n', header=None)
        else:
            playlist_data = pd.read_csv(localmusicpath_prefix + name + 
                                        '/' + name + '_playlist.txt', 
                                        sep='\n', header=None)
    except:
        print("Playlist was not found. Updating playlists.")
        update_playlists([name], False)
        if name == 'other':
            playlist_data = pd.read_csv(localmusicpath_prefix + name + '_playlist.txt', 
                                        sep='\n', header=None)
        else:
            playlist_data = pd.read_csv(localmusicpath_prefix + name + 
                                        '/' + name + '_playlist.txt', 
                                        sep='\n', header=None)
    playlist = playlist_data[0].tolist()
    return playlist


def playlist_duration(plist):
    """Determines the total duration of the playlist."""
    total_duration = 0
    for song in plist:
        if len(plist) >= 10:
            # If playlists contain too many songs, calculating the total
            # duration takes too much time, so it's set to some constant 
            # here. 
            total_duration = 69420
            break
        else:
            total_duration += probe_file(localmusicpath_prefix + song)
    return total_duration


def update_playlists(listnames, autoshuffle):
    """Update local playlists for music bot. Music files outside of
    dedicated folders are put into a playlist named 'other'. """
    if 'other' in listnames:
        listnames.pop(listnames.index('other'))
    for listname in listnames:
        musiclist = []
        for filename in os.listdir(localmusicpath_prefix + listname):
            if not filename.startswith('.') and not filename.endswith('.txt'):
                musiclist.append(listname + '/' + filename)
        if autoshuffle:
            shuffle(musiclist)
        else:
            musiclist.sort()
        make_playlist(listname)
        for i in range(len(musiclist)):
            add_to_playlist(listname, musiclist[i])

    songs = []
    for filename in os.listdir(localmusicpath_prefix):
        for filetype in filetype_extensions:
            if filename.endswith(filetype):
                songs.append(filename)

    make_playlist('other')
    for i in range(len(songs)):
        add_to_playlist('other', songs[i])
    listnames.append('other')
    print('Playlists updated.')


def cleanup_filename(name):
    """Removes unnecessary parts of filenames."""
    
    # Sort the playlist names to make sure the longest names are
    # iterated through first.
    ordered_plist_names = sorted(plist_names, key=len, reverse=True)
    for listname in ordered_plist_names:
        if name.startswith(listname):
            name = name[(len(listname)+1):]
    if name.startswith('youtube'):
        name = name[20:]
    name = name.translate ({ord(c): " " for c in "@#$%^*{};:/<>?\|`=_+"})
    for filetype in filetype_extensions:
        if name.endswith(filetype):
            name = name[:-(len(filetype))]
    return name


def RepresentsInt(string):
    """Checks if string is an integer."""
    try:
        int(string)
        return True
    except ValueError:
        return False


def format_playtime(seconds):
    """Converts a float value to a string in HH:MM:SS format."""
    return time.strftime('%H:%M:%S',time.gmtime(seconds))



class Music(commands.Cog):
    """Discord extension class that handles music playback inside 
    discord voice channels."""
    def __init__(self, bot):
        self.bot = bot
        
        # defaults from settings:

        self.playlist = read_playlist(bot_settings.default_playlist)
        self.playlist_name = bot_settings.default_playlist
        self.autoshuffle = bot_settings.default_autoshuffle
        self.showwaveforms = bot_settings.default_showwaveforms
        self.volume = bot_settings.default_volume
        self.fadein = bot_settings.default_fade_in
        self.fadeout = bot_settings.default_fade_out
        self.t_msgdelete = bot_settings.default_msgdelete_time
        self.verbose = bot_settings.verbose

        self.textchannel_updated = False
        self.volume_fade = self.volume
        self.fade_steps = 30
        self.fading = False
        self.allow_yt = True
        self.task = None
        self.now_playing = None
        self.play_start_time = None
        self.song_duration = None
        self.song_progress = 0.0
        self.paused = False
        self.time_paused = 0.0
        self.time_unpaused = 0.0
        self.next_song = None
        self.prev_msg = None
        self.np_msg = None
        self.np_embed = None
        self.plist_length = len(self.playlist)


    @commands.command()
    async def fadeout(self, ctx, *, steps: int =13):
        '''Fade out the music volume to (almost) zero.'''
        if ctx.voice_client != None and self.now_playing != None and self.fading is False:
            try:
                self.fading = True
                self.volume_fade = self.volume
                if steps == 13:
                    steps = self.fade_steps
                for step in range(steps):
                    # # Linear:
                    # ctx.voice_client.source.volume = self.volume * ((steps - (step + 1)) / steps)
                    # Logarithmic:
                    ctx.voice_client.source.volume = self.volume * (-math.log(((step+1)/steps)/1.58 + 1/math.exp(1)))
                    # print(step, "[FADETEST] Volume = ", ctx.voice_client.source.volume)
                    await asyncio.sleep(1/(1.0*steps))
                # self.volume = 0.0
                self.fading = False
            except:
                pass
                return
        else:
            print("[FADEOUT] no music is playing")


    @commands.command()
    async def fadein(self, ctx, *, steps: int =13):
        '''Fade music volume back up to its value before it was faded out.'''
        if ctx.voice_client != None and self.now_playing != None and self.fading is False:
            try:
                self.fading = True
                if steps == 13:
                    steps = self.fade_steps
                for step in range(steps):
                        # # Linear:
                        # ctx.voice_client.source.volume = self.volume * ((step + 1) / steps)
                        # Logarithmic:
                        ctx.voice_client.source.volume = self.volume_fade * (-math.log(((steps-(step+1))/steps)/1.58 + 1/math.exp(1)))
                        # print(step, "[FADETEST] Volume = ", ctx.voice_client.source.volume)
                        await asyncio.sleep(1/(1.0*steps))
                self.volume = ctx.voice_client.source.volume
                self.fading = False
            except:
                pass
                return
        else:
            print("[FADEIN] no music is playing")


    @commands.group()
    async def move(self, ctx):
        """Moves song(s) to other playlist."""
        if ctx.invoked_subcommand is None:
            await ctx.send("You need to specify what you want to move, and where. \
                \nFor example, <.move song mysterious> moves the currently playing song to the mysterious playlist.")


    @move.command()
    async def song(self, ctx, *, targetplaylist:str):
        """Moves current song to other playlist."""
        try:
            current_song = localmusicpath_prefix + self.now_playing
            target_song = localmusicpath_prefix + targetplaylist + "/" + self.now_playing[len(self.playlist_name)+1:]
        except:
            movemsg = await ctx.send("It was not possible to move this song.")
            await discord.Message.delete(movemsg, delay=self.t_msgdelete)
            raise

        os.rename(current_song, target_song)
        
        # global plist_names
        update_playlists(plist_names, self.autoshuffle)
        song_name = cleanup_filename(self.now_playing)
        movemsg = await ctx.send("{} sent to {}.".format(song_name, targetplaylist))
        await discord.Message.delete(movemsg, delay=self.t_msgdelete)


    def song_msg(self, total_duration=0, playlist=[]):
        """Prepares the embedded message that announces a new song"""
        if playlist==[]:
            playlist = read_playlist(self.playlist_name)
        url = "https://www.google.com/search?q="+cleanup_filename(self.now_playing).replace(' ','%20')
        embed = discord.Embed(title="Now Playing", url=url, color=0xad3e00)
        embed.add_field(name="Song name:", value=cleanup_filename(self.now_playing), inline=True)
        embed.add_field(name="Playlist:", value=self.playlist_name, inline=True)
        embed.add_field(name="# of songs left:", value="{}/{}".format(len(self.playlist),self.plist_length))
        embed.add_field(name="Song duration:", value="{}".format(format_playtime(self.song_duration)))
        embed.add_field(name="Playlist duration:", value="{}".format(format_playtime(total_duration)), inline=True)
        embed.add_field(name="Volume:", value='{}%'.format(int(self.volume_fade*100)))
        embed.add_field(name="Next song:", value=cleanup_filename(self.next_song))
        embed.add_field(name="Autoshuffle:", value="ON" if self.autoshuffle else "OFF")
        embed.set_footer(text="Check the music queue with <q> and available playlists with <pl>.")
        return embed


    @commands.command()
    async def stats(self, ctx):
        """List several music related stats of the bot."""
        stats_totalnumsongs = 0
        stats_total_duration = 0
        for i in range(len(plist_names)):
            plist = read_playlist(plist_names[i])
            stats_totalnumsongs += len(plist)

        embed = discord.Embed(title="Music Statistics",color=0xad3e00)
        embed.add_field(name="Total # of songs:",value=stats_totalnumsongs)

        if self.verbose:
            statsmsg = await text_channel.send(content=None, embed=embed)
            await discord.Message.delete(statsmsg, delay=self.t_msgdelete)


    def update_song_progress(self):
        """Update the song's current progress."""
        current_time = time.time()
        if self.paused:
            time_elapsed = self.song_progress
            status = ' (currently paused)'
        else:
            time_elapsed = current_time - (self.play_start_time + (self.time_unpaused))
            status = ''
        self.song_progress = time_elapsed
        
        # Update embedded message
        embed = self.song_msg(playlist=self.playlist)
        embed.remove_field(4)
        embed.insert_field_at(3, name="Progress:", value="{}{}".format(format_playtime(self.song_progress), status), inline=True)
        self.np_embed = embed
        return embed


    @commands.command()
    async def yt(self, ctx, *, yt_url):
        '''Downloads a song from YouTube and adds it to the "yt" playlist.'''
        if self.allow_yt:
            if yt_url.startswith('https://youtu') or yt_url.startswith('https://www.youtu'):
                if "playlist" in yt_url or "list=" in yt_url and self.verbose:
                    yt_pl_msg = await text_channel.send("Starting to download playlist...")
                    await discord.Message.delete(yt_pl_msg, delay=self.t_msgdelete)
                songname, dl_success = yt_dl(yt_url)
                query = cleanup_filename(songname)
                if self.verbose:
                    if dl_success:
                        yt_msg = await text_channel.send("Download of " + query + " attempted. \nAdding song to 'yt' playlist...")
                        await discord.Message.delete(yt_msg, delay=self.t_msgdelete)
                    else:
                        yt_msg = await text_channel.send("Download failed. It's probably a popular song that YouTube restricts access to.")
                        await discord.Message.delete(yt_msg, delay=self.t_msgdelete)
                        return
                await asyncio.sleep(3)
                commandcheck = self.bot.get_command('check_playlists')
                await ctx.invoke(commandcheck)

                self.playlist = read_playlist('yt')
                self.playlist_name = 'yt'
                channel = self.bot.get_channel(voice_channel_id)
                commandjoin = self.bot.get_command('join')
                await ctx.invoke(commandjoin, channel=channel)
                commandplay = self.bot.get_command('play')
                await ctx.invoke(commandplay, query='yt/'+songname)
            else:
                yt_msg = await text_channel.send("That doesn't appear to be a YouTube link.")
                await discord.Message.delete(yt_msg, delay=self.t_msgdelete)
        else:
            yt_msg = await text_channel.send("Youtube song download is currently disabled.")
            await discord.Message.delete(yt_msg, delay=self.t_msgdelete)


    @commands.command()
    @commands.is_owner()
    async def clear_yt(self, ctx):
        '''Clears the youtube playlist and deletes downloaded files.'''
        if self.playlist_name == 'yt':
            commandstop = self.bot.get_command('stop')
            await ctx.invoke(commandstop)
        for root, dirs, files in os.walk(localmusicpath_prefix + '/yt'):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))
        if self.verbose:
            clear_msg = await text_channel.send('Downloaded songs have been deleted.')
            await discord.Message.delete(clear_msg, delay=self.t_msgdelete)
        commandcheck = self.bot.get_command('check_playlists')
        await ctx.invoke(commandcheck)


    @commands.command(aliases=['autosh'])
    async def autoshuffle(self, ctx):
        """Toggle autoshuffle. Alias: <autosh>"""
        if not self.autoshuffle:
            self.autoshuffle = True
            print('Autoshuffle on')
            if verbose:
                shufflemsg = await text_channel.send('**Autoshuffle:** ON')
        else:
            self.autoshuffle = False
            print('Autoshuffle off')
            if self.verbose:
                shufflemsg = await text_channel.send('**Autoshuffle:** OFF')
        if verbose:
            await discord.Message.delete(shufflemsg, delay=self.t_msgdelete)


    @commands.command(aliases=['verb'])
    async def verbose(self, ctx):
        """Toggle verbose responses from the bot."""
        if not self.verbose:
            self.verbose = True
            print('Verbose responses on')
            verbosemsg = await text_channel.send('**Verbose:** ON')
        else:
            self.verbose = False
            print('Verbose responses off')
            verbosemsg = await text_channel.send('**Verbose:** OFF')
        await discord.Message.delete(verbosemsg, delay=self.t_msgdelete)


    @commands.is_owner()
    @commands.command(aliases=['tyt'])
    async def toggle_yt(self, ctx):
        """Enable/disable Youtube download with the <yt> command."""
        if not self.allow_yt:
            self.allow_yt = True
            print('YT downloads enabled')
            tytmsg = await text_channel.send('**Youtube song download:** ON')
        else:
            self.allow_yt = False
            print('YT downloads disabled')
            tytmsg = await text_channel.send('**Youtube song download:** OFF')
        await discord.Message.delete(tytmsg, delay=self.t_msgdelete)


    @commands.command(aliases=['autopl'])
    async def autoplaylist(self, ctx):
        """Toggle auto playlist, and updates playlists."""
        global plist_names
        if not bot_settings.manual_playlist_selection:
            bot_settings.manual_playlist_selection = True
            plist_names = bot_settings.manual_playlists
            print('Autoplaylist on')
            if self.verbose:
                pl_msg = await text_channel.send('**Autoplaylist:** ON')
        else:
            bot_settings.manual_playlist_selection = False
            plist_names = fetch_playlists()
            print('Autoplaylist off')
            if self.verbose:
                pl_msg = await text_channel.send('**Autoplaylist:** OFF')
        update_playlists(plist_names, self.autoshuffle)
        if self.verbose:
            await discord.Message.delete(pl_msg, delay=self.t_msgdelete)


    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel =None):
        """Joins a voice channel and sets it as the default."""
        global voice_channel_id
        author = ctx.author
        if channel == None:
            vchannels = ctx.guild.voice_channels
            for vchannel in vchannels:
                for member in vchannel.members:
                    if member.id == author.id:
                        voice_channel_id = vchannel.id
                        break
        
        else:        
            voice_channel_id = channel.id
        channel = self.bot.get_channel(voice_channel_id)
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        await channel.connect()


    @commands.command()
    async def textchannel(self, ctx, *, channel: discord.TextChannel =None):
        """Joins a text channel and sets it as the default."""
        global text_channel
        author = ctx.author
        if channel == None:
            tchannel = ctx.channel
            text_channel = self.bot.get_channel(tchannel.id)
        else:        
            text_channel = self.bot.get_channel(text_channel_id)
        self.textchannel_updated = True
        txtmsg = await text_channel.send("Connected to " + text_channel.name + ", {}.".format(ctx.author.mention))
        await discord.Message.delete(txtmsg, delay=self.t_msgdelete)


    @commands.command()
    async def summon(self, ctx):
        """Summons and binds the bot to your current voice and text channel. """
        commandjoin = self.bot.get_command('join')
        commandtextchannel = self.bot.get_command('textchannel')
        await ctx.invoke(commandjoin)
        await ctx.invoke(commandtextchannel)


    async def increment_playlist(self, ctx):
        """Increments playlist by 1 and makes it repeat if it has 1 song
        left."""
        if len(self.playlist) <= 1:
            commandcancel = self.bot.get_command('cancel_next_song')
            await ctx.invoke(commandcancel)
            if self.playlist_name == 'loop':
                self.playlist = self.playlist + [self.now_playing, self.now_playing]
            else:
                self.playlist = self.playlist + read_playlist(self.playlist_name)
            print('Playlist recycled. Number of songs:', len(self.playlist))
            self.playlist.pop(0)
            self.next_song = self.playlist[0]
            if self.autoshuffle:
                shuffle(self.playlist)
                print("(AUTOSHUFFLE) Shuffle completed.")
        else:
            self.playlist.pop(0)
            self.next_song = self.playlist[0]


    @commands.command()
    async def play(self, ctx, *, query, before: str ='-ss 00:00:00', autoplay: bool =False):
        """Plays a file from the local filesystem."""

        # "Spam skip" or rapid playlist swapping protection:
        if self.fading:
            return

        # Get proper filepath, song duration, and cleaned up name.
        abs_query = localmusicpath_prefix + query
        self.song_duration = probe_file(abs_query)
        query_name = cleanup_filename(query)

        # Set fade-in and fade-out filter options and obtain music 
        # source with the correct volume.
        after_options = ("-filter_complex 'afade=t=in:ss=0:d=" + str(self.fadein) + ",afade=t=out:st=" + str(self.song_duration) + ":d=" + str(self.fadeout) + ",equalizer=f=3000:t=h:width=1000:g=-6'")
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(abs_query, before_options=before, options=after_options))
        source.volume = self.volume

        # If the play command was not triggered automatically, fade out 
        # the current song.
        if not autoplay:
            commandfadeout = self.bot.get_command('fadeout')
            await ctx.invoke(commandfadeout)

        # Start song playback, whether a song was already playing or 
        # not.
        if ctx.voice_client.is_playing():
            commandcancel = self.bot.get_command('cancel_next_song')
            await ctx.invoke(commandcancel)
            ctx.voice_client.source = source
        else:
            ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else print('Song ended.'))
        print("(PLAY) Starting playback of: " + query_name)

        self.now_playing = query

        # Update bot's status message.
        await self.bot.change_presence(status=discord.Status.online, activity=discord.Game(query_name))        
        
        # Prepare variables required to track pause duration.
        self.play_start_time = time.time()
        self.time_paused = 0.0
        self.time_unpaused = 0.0

        # Update playlist.
        await self.increment_playlist(ctx)

        # Send embedded overview of music player
        if self.verbose and not self.fading:
            async with text_channel.typing():
                total_duration = playlist_duration(self.playlist)
                embed = self.song_msg(total_duration=total_duration, playlist=self.playlist)
                songmsg = await text_channel.send(content=None, embed=embed)
                await discord.Message.delete(songmsg, delay=self.t_msgdelete)
        else:
            total_duration = playlist_duration(self.playlist)
        
        # Schedule playback of next song.
        commandnext_song = self.bot.get_command('next_song')
        self.task = asyncio.create_task(ctx.invoke(commandnext_song, query=self.next_song, song_duration=self.song_duration))


    @commands.command(aliases=['lp'])
    async def loop(self, ctx):
        """Endlessly loops the currently playing song."""
        if self.now_playing != None:
            self.playlist_name = 'loop'
            self.playlist = [self.now_playing, self.now_playing]
            self.plist_length = len(self.playlist)
            self.next_song = self.now_playing
            self.update_song_progress()
            new_duration = self.song_duration - self.song_progress
            try:
                if not self.task.cancelled():
                    commandcancel = self.bot.get_command('cancel_next_song')
                    await ctx.invoke(commandcancel)
            except:
                print("(FWD) Error during cancelling task.")
                pass

            commandnext_song = self.bot.get_command('next_song')
            self.task = asyncio.create_task(ctx.invoke(commandnext_song, query=self.now_playing, song_duration=new_duration))
            songname = cleanup_filename(self.now_playing)
            print("(LOOP) Created a looped playlist for " + songname)
            if self.verbose:
                loopmsg = await text_channel.send("The current song will be repeated. Endlessly.")
                await discord.Message.delete(loopmsg, delay=self.t_msgdelete)


    @commands.command(aliases=['f'])
    async def forward_skip(self, ctx, *, tstart: int =10):
        """Forwards the current song by 10 sec or more. Alias: <f>"""
        if self.now_playing != None:
            self.update_song_progress()
            self.song_progress += tstart
            if self.song_progress < 0:
                self.song_progress = 0.0
                self.play_start_time = time.time()
                self.time_unpaused = 0.0
            else:
                self.time_unpaused -= tstart

            new_duration = self.song_duration - self.song_progress
            
            timestr = format_playtime(self.song_progress)
            durationstr = format_playtime(self.song_duration)
            before = '-ss ' + timestr
            
            abs_query = localmusicpath_prefix + self.now_playing
            query_name = cleanup_filename(self.now_playing)
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(abs_query, before_options=before))
            source.volume = self.volume
            
            if new_duration < 0:
                # Skip to next song if forwarding further than the
                # remaining song duration.
                commandplay = self.bot.get_command('play')
                await ctx.invoke(commandplay, query=self.next_song)
            else:
                if ctx.voice_client.is_playing():
                    try:
                        if not self.task.cancelled():
                            commandcancel = self.bot.get_command('cancel_next_song')
                            await ctx.invoke(commandcancel)
                    except:
                        print("(FWD) Error during cancelling task.")
                        pass
                    ctx.voice_client.source = source
                else:
                    ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else print('Song ended.'))
                
                print('(FWD) Song forwarded to {}.'.format(timestr))
                if self.verbose:
                    forwardmsg = await text_channel.send("Song forwarded to {}/{}".format(timestr,durationstr))
                    await discord.Message.delete(forwardmsg, delay=self.t_msgdelete)

                commandnext_song = self.bot.get_command('next_song')
                self.task = asyncio.create_task(ctx.invoke(commandnext_song, query=self.next_song, song_duration=new_duration))
                print("(FWD) Preparing next song:", cleanup_filename(self.next_song))
        else:
            nosongmsg = await text_channel.send("I need to be playing music in order to forward a song.")
            await discord.Message.delete(nosongmsg, delay=self.t_msgdelete)


    @commands.command(aliases=['skip'])
    async def next_song(self, ctx, *, query=None, song_duration: int =0, before: str ='-ss 00:00:00'):
        """Skips this song.  Alias: <skip>"""
        if query == None:
            query = self.next_song

        # Wait until current song has ended.
        try:
            await asyncio.sleep(song_duration)
            print('Playing next song...')
            self.task = None
            commandplay = self.bot.get_command('play')
            await ctx.invoke(commandplay, query=query, before=before, autoplay=True)
        except asyncio.CancelledError:
            print('(SKIP) Cancelling playback of: {}...'.format(cleanup_filename(self.next_song)))
            raise


    @commands.command(aliases=['c'])
    async def cancel_next_song(self, ctx):
        """Cancels playing the next song."""
        if self.task is not None:
            
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                if self.task.cancelled():
                    canceltext = '(SKIP) Successfully cancelled'
                else:
                    canceltext = '(SKIP) Successfully cancelled (maybe)'
                print(canceltext)
        else:
            print('[SKIP] No tasks to cancel.')


    @commands.command(aliases=['p'])
    async def playlist(self, ctx, *, playlist='default'):
        """Play a specific playlist.  Alias: <p>"""

        channel = self.bot.get_channel(voice_channel_id)
        commandjoin = self.bot.get_command('join')
        await ctx.invoke(commandjoin, channel=channel)
        
        if RepresentsInt(playlist):
            if int(playlist) - 1 > len(plist_names):
                pllengthmsg = await text_channel.send("There aren't that many playlists! Use <pl> to view the current playlists.")
                await discord.Message.delete(pllengthmsg, delay=self.t_msgdelete)
            else:
                playlist = plist_names[int(playlist) - 1]

        # Play a random playlist:
        if playlist in ['x', '?', 'r', 'rand', 'random']:
            playlist = choice(plist_names)
        elif not playlist in plist_names:
            unknownplmsg = await text_channel.send("I don't know that playlist. Did you misspell it? You can also check current playlists with <pl>.")
            await discord.Message.delete(unknownplmsg, delay=self.t_msgdelete)
            return
        
        self.playlist = read_playlist(playlist)
        self.plist_length = len(self.playlist)
        if self.autoshuffle:
            shuffle(self.playlist)
            print("(AUTOSHUFFLE) Shuffle completed.")
        self.next_song = self.playlist[0]
        self.playlist_name = playlist

        commandplay = self.bot.get_command('play')
        await ctx.invoke(commandplay, query=self.next_song)


    @commands.command(aliases=['sh'])
    async def shuffle(self, ctx):
        """Shuffle playlist.  Alias: <sh>"""
        print("(SHUFFLE) Shuffling...")
        if ctx.voice_client.is_playing():
            commandcancel = self.bot.get_command('cancel_next_song')
            await ctx.invoke(commandcancel)

        shuffle(self.playlist)
        self.next_song = self.playlist[0]

        self.update_song_progress()
        start_next_song = self.song_duration - self.song_progress

        commandnext_song = self.bot.get_command('next_song')
        self.task = asyncio.create_task(ctx.invoke(commandnext_song, query=self.next_song, song_duration=start_next_song))
        print("(SHUFFLE) Shuffling completed.")
        
        query = self.next_song
        query_name = cleanup_filename(query)
        print('Next song:',query_name)
        
        if self.verbose:
            shufflemsg = await text_channel.send('Playlist shuffled!')
            await discord.Message.delete(shufflemsg, delay=self.t_msgdelete)


    @commands.command(aliases=['ps', 's'])
    async def playlist_skip_to(self, ctx, *args):
        """Skip a number of songs in a playlist. Alias: <ps>"""

        hasNumber = True
        hasPlaylist = True
        try:
            if RepresentsInt(args[0]):
                skipnum = int(args[0])
            else:
                skipnum = 1
        except:
            skipnum = 1
            hasNumber = False
            pass
        try:
            playlist_name = args[1]
        except:
            playlist_name = 'std'
            hasPlaylist = False
            pass

        if playlist_name == 'std':
            playlist_name = self.playlist_name
            playlist = self.playlist
        else:
            playlist = read_playlist(playlist_name)

        if skipnum > len(playlist):
            queuelengthmsg = await text_channel.send("The music queue doesn't have that many songs! Use <q> to view the current queue.")
            await discord.Message.delete(queuelengthmsg, delay=self.t_msgdelete)
        elif self.now_playing is None:
            nosongmsg = await text_channel.send("I'm not playing any music right now, so I " +
                           "can't skip a song in a playlist. \nYou " +
                           "can browse the available playlists with " +
                           "<pl>.")
            await discord.Message.delete(nosongmsg, delay=self.t_msgdelete)
        else:
            if (playlist_name != self.playlist_name) or (hasNumber and hasPlaylist):
                self.playlist_name = playlist_name
                self.playlist = playlist

            if not self.fading:
                commandcancel = self.bot.get_command('cancel_next_song')
                await ctx.invoke(commandcancel)

                for num in range(skipnum-1):
                    await self.increment_playlist(ctx)
                
                query_name = cleanup_filename(self.next_song)
                if self.verbose:
                    skipmsg = await text_channel.send('Skipping to song {} on the queue: {}'.format(skipnum, query_name))
                    await discord.Message.delete(skipmsg, delay=self.t_msgdelete)

                commandplay = self.bot.get_command('play')
                await ctx.invoke(commandplay, query=self.next_song)


    @commands.command(aliases=['a'])
    async def add_song(self, ctx, *args):
        """Add a song to the current playlist. Alias: <a>"""

        hasNumber = True
        hasPlaylist = True
        try:
            if RepresentsInt(args[0]):
                skipnum = int(args[0])
            else:
                skipnum = 1
        except:
            skipnum = 1
            hasNumber = False
            pass
        try:
            playlist_name = args[1]
        except:
            playlist_name = 'std'
            hasPlaylist = False
            pass

        if playlist_name == 'std':
            playlist_name = self.playlist_name
            playlist = self.playlist
        else:
            playlist = read_playlist(playlist_name)

        if skipnum > len(playlist):
            queuelengthmsg = await text_channel.send("The music queue doesn't have that many songs! Use <q> to view the current queue.")
            await discord.Message.delete(queuelengthmsg, delay=self.t_msgdelete)
        elif self.now_playing is None:
            nosongmsg = await text_channel.send("I'm not playing any music right now, so I " +
                           "can't add this song to the playlist. \nYou " +
                           "can browse the available playlists with " +
                           "<pl>.")
            await discord.Message.delete(nosongmsg, delay=self.t_msgdelete)
        else:
            if not self.fading:
                self.playlist.append(playlist[skipnum-1])
                
                query_name = cleanup_filename(playlist[skipnum-1])
                if self.verbose:
                    addmsg = await text_channel.send('Added {} to the queue.'.format(query_name))
                    await discord.Message.delete(addmsg, delay=self.t_msgdelete)


    @commands.command(aliases=['cp'])
    async def check_playlists(self, ctx):
        """Update local playlists. Alias: <cp>"""
        global plist_names
        if bot_settings.manual_playlist_selection:
            plist_names = bot_settings.manual_playlists
        else:
            plist_names = fetch_playlists()
        update_playlists(plist_names, self.autoshuffle)
        if not self.textchannel_updated:
            text_channel_id = bot_settings.text_channel_id
            global text_channel
            text_channel = self.bot.get_channel(text_channel_id)
        plupdatemsg = await text_channel.send('Playlists have been updated.')
        await discord.Message.delete(plupdatemsg, delay=self.t_msgdelete)


    @commands.command(aliases=['pl'])
    async  def show_playlists(self, ctx):
        """Show all known playlists. Alias: <pl>"""
        messages = {"msg0": '**Known playlists:**' + '\n'}
        pl_msg = "msg0"
        msg_num = 1
        for i in range(len(plist_names)):
            messages[pl_msg] = messages[pl_msg] + str(i+1) + ". " + plist_names[i] + "\n"
            if len(messages[pl_msg]) > 1950:
                messages[pl_msg] = messages[pl_msg][:(len(messages[pl_msg]) - (len(str(i+1)) + 4 + len(plist_names[i])+1))]
                msg_num += 1
                pl_msg = "msg" + str(msg_num)
                messages[pl_msg] = str(i+1) + ". " + plist_names[i] + "\n"

        print('Sending list of playlists to discord...')
        for message in messages.values():
            playlistsmsg = await text_channel.send(message[:-1])
            await discord.Message.delete(playlistsmsg, delay=self.t_msgdelete)


    @commands.command(aliases=['np'])
    async def now_playing(self, ctx):
        """Displays current song and elapsed play time. Alias: <np>"""
        if self.now_playing is not None:
            
            embed = self.update_song_progress()
            self.np_msg = await text_channel.send(content=None, embed=embed)
            
            for t in range(self.t_msgdelete):
                await asyncio.sleep(1)
                embed = self.update_song_progress()
    
                try:
                    await discord.Message.edit(self.np_msg, content=None, embed=embed, delete_after=self.t_msgdelete)
                except:
                    print('deleting previous now_playing message')
                    await discord.Message.delete(self.np_msg, delay=0)
                    pass
                    break
        else:
            print('No song playing')
            nosongmsg = await text_channel.send("There aren't any songs being played right now. So quiet...")
            await discord.Message.delete(nosongmsg, delay=self.t_msgdelete)


    @commands.command(aliases=['q'])
    async def queue(self, ctx, *, playlist_name: str ='std'):
        """Display music queue of current playlist. Alias: <q>"""
        if RepresentsInt(playlist_name):
            if int(playlist_name) - 1 > len(plist_names):
                pllengthmsg = await text_channel.send("There aren't that many playlists! Use <pl> to view the current playlists.")
                await discord.Message.delete(pllengthmsg, delay=self.t_msgdelete)
            else:
                playlist_name = plist_names[int(playlist_name) - 1]
                playlist = read_playlist(playlist_name)

        elif playlist_name == 'std':
            playlist_name = self.playlist_name
            playlist = self.playlist
        else:
            playlist = read_playlist(playlist_name)

        messages = {"msg0": '**Playlist:** ' + playlist_name + '\n' + "**Current queue:**\n"}
        q_msg = "msg0"
        msg_num = 1
        for i in range(len(playlist)):
            songname = cleanup_filename(playlist[i])
            messages[q_msg] = messages[q_msg] + str(i+1) + ". " + songname + "\n"
            if len(messages[q_msg]) > 1950:
                messages[q_msg] = messages[q_msg][:(len(messages[q_msg]) - (len(str(i+1)) + 4 + len(songname)+1))]
                msg_num += 1
                q_msg = "msg" + str(msg_num)
                messages[q_msg] = str(i+1) + ". " + songname + "\n"

        print('Sending music queue to discord...')
        for message in messages.values():
            queuemsg = await text_channel.send(message[:-1])
            await discord.Message.delete(queuemsg, delay=self.t_msgdelete)


    @commands.command()
    async def pause(self, ctx):
        """Pauses music player."""
        if ctx.voice_client == None:
            novoicemsg = await text_channel.send("I'm not connected to a voice channel, so there's nothing to pause.")
            await discord.Message.delete(novoicemsg, delay=self.t_msgdelete)
        else:
            self.update_song_progress()

            current_time = time.time()
            self.paused = True
            self.time_paused = current_time
            
            commandcancel = self.bot.get_command('cancel_next_song')
            asyncio.create_task(ctx.invoke(commandcancel))
            if ctx.voice_client.is_playing():
                ctx.voice_client.pause()


    @commands.command(aliases=['unpause'])
    async def resume(self, ctx):
        """Resumes music player."""

        start_next_song = self.song_duration - self.song_progress
        self.paused = False
        self.time_unpaused += time.time() - self.time_paused

        if self.next_song is not None:
            commandnext_song = self.bot.get_command('next_song')
            self.task = asyncio.create_task(ctx.invoke(commandnext_song, query=self.next_song, song_duration=start_next_song))
        ctx.voice_client.resume()


    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice."""
        commandcancel = self.bot.get_command('cancel_next_song')
        await ctx.invoke(commandcancel)

        if self.task != None:
            if not self.task.cancelled():
                print('[STOP] Cancelling task has failed.')

        if ctx.voice_client is None:
            noconnectmsg = await text_channel.send("Not connected to a voice channel.")
            await discord.Message.delete(noconnectmsg, delay=self.t_msgdelete)
            return 
        else:
            self.now_playing = None
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game('Zzz...'))
            await ctx.voice_client.disconnect()


    @commands.command(aliases=['v'])
    async def volume(self, ctx, volume: int):
        """Changes the player's volume. Alias: <v>"""

        if ctx.voice_client is None:
            noconnectmsg = await text_channel.send("Not connected to a voice channel.")
            await discord.Message.delete(noconnnectmsg, delay=self.t_msgdelete)
            return 

        self.volume = volume / 100
        self.volume_fade = self.volume
        ctx.voice_client.source.volume = volume / 100
        volumemsg = await text_channel.send("Changed volume to {}%".format(volume))
        await discord.Message.delete(volumemsg, delay=self.t_msgdelete)



    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                novoicemsg = await text_channel.send("You are not connected to a voice channel.")
                await discord.Message.delete(novoicemsg, delay=self.t_msgdelete)
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


    @loop.after_invoke
    @song.after_invoke
    @join.after_invoke
    @playlist.after_invoke
    @queue.after_invoke
    @now_playing.after_invoke
    @playlist_skip_to.after_invoke
    @check_playlists.after_invoke
    @show_playlists.after_invoke
    @forward_skip.after_invoke
    @pause.after_invoke
    @resume.after_invoke
    @volume.after_invoke
    @cancel_next_song.after_invoke
    @shuffle.after_invoke
    @autoshuffle.after_invoke
    @autoplaylist.after_invoke
    @stop.after_invoke
    @yt.after_invoke
    @clear_yt.after_invoke
    @stats.after_invoke
    @verbose.after_invoke
    @textchannel.after_invoke
    @summon.after_invoke
    @toggle_yt.after_invoke
    @add_song.after_invoke
    async def remove_command_msg(self, ctx):
        """Removes the messages of users after completing the 
        requested command."""
        global dont_delete
        if dont_delete:
            dont_delete = False
            return
        else:
            await discord.Message.delete(ctx.message, delay=5)

    
    @commands.Cog.listener()
    async def on_ready(self):
        print('-> MusicPlayer: Ready to play music.')
        text_channel_id = bot_settings.text_channel_id
        global text_channel
        text_channel = self.bot.get_channel(text_channel_id)

        if bot_settings.manual_playlist_selection:
            global plist_names
            plist_names = bot_settings.manual_playlists
        update_playlists(plist_names, self.autoshuffle)


def setup(client):
    client.add_cog(Music(client))
