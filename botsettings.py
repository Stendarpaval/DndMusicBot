from os.path import dirname, abspath

class Settings():
    """A class to store all settings for your discord bot."""

    def __init__(self):
        """Initialize settings."""

        # General settings.
        self.command_prefixes = ['.','`']
        currentdirectory = dirname(abspath(__file__))
        self.extension_folder = currentdirectory + '/extensions'
        self.TOKEN = 'yourBotsDiscordToken'
        self.owner_id = 000

        # MusicPlayer settings.
        self.localmusicpath_prefix = 'full/path/to/music/library' 
        self.filetype_extensions = ['.mp3', '.mp4a', '.m4a', '.m4r', '.webm', '.opus']
        self.voice_channel_id = 000
        self.text_channel_id = 000
        
        self.verbose = True
        self.default_autoshuffle = True
        self.default_showwaveforms = False
        self.default_msgdelete_time = 25
        self.default_playlist = 'default'
        self.default_volume = 0.15
        self.default_fade_in = 5
        self.default_fade_out = 5

        self.manual_playlist_selection = False
        self.manual_playlists = [
                                'default',
                                'yt',
                                'or any other playlist folder in your music library',
                                ]

  