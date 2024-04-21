
import re
import subprocess
import collections
import logging
from vimsaver.multiplexers import Multiplexer

ScreenWinTuple = collections.namedtuple( 'ScreenWinTuple', ['idx', 'title'] )

PATTERN_PTS_SCREEN = re.compile( r':\S*:S.(?P<screen>[0-9]*)' )
PATTERN_SCREEN_NUMBER = re.compile(
    r'(?P<idx>[0-9]*)\s*\((?P<title>[A-Za-z0-9]*)\)' )

class GNUScreen( Multiplexer ):

    @staticmethod
    def window_from_pty( pty_from : str ) -> int:

        logger = logging.getLogger( 'multiplexers.gnu_screen.window_from_pty' )

        pty_screen = PATTERN_PTS_SCREEN.match( pty_from )
        if not pty_screen:
            return None

        window_num = int( pty_screen.group( 'screen' ) )

        logger.debug( 'PTY %s is screen: %d', pty_from, window_num )

        return window_num

    def __init__( self, session : str ):
        self.session = session

    def screen_command( self, window : int, command : list ):
        logger = logging.getLogger( 'multiplexers.gnu_screen.command' )
        screenc = ['screen', '-S', self.session, '-X']
        if 0 <= window:
            screenc += ['-p', str( window )]
        screenc += command
        logger.debug( screenc )
        screenp = subprocess.run( screenc )

    def get_window_title( self, idx : int ):

        screenp = subprocess.Popen(
            ['screen', '-S', self.session, '-p', str( idx ), '-Q', 'number'],
            stdout=subprocess.PIPE )

        lines_out = []
        word_idx = 0
        match = PATTERN_SCREEN_NUMBER.match(
            screenp.stdout.read().decode( 'utf-8' ) )

        if match:
            return match.groupdict()['title']

        return None

    def set_window_title( self, idx : int, title : str ):

        screenp = subprocess.Popen(
            ['screen', '-S', self.session, '-p', idx, '-X', 'title', title],
            stdout=subprocess.PIPE )

    def send_shell( self, command : list, window : int ):
        logger = logging.getLogger( 'multiplexers.gnu_screen.send_shell' )
        logger.debug( 'sending shell command: %s', str( command ) )
        command[-1] =  command[-1] + '^M'
        self.screen_command( window, ['stuff'] + [' '.join( command )] )

    def new_window( self, window : int ):
        logger = logging.getLogger( 'multiplexers.gnu_screen.new_window' )
        logger.debug( 'opening window %s in screen...', window )
        self.screen_command( -1, ['screen', window] )

MULTIPLEXER_CLASS = GNUScreen

