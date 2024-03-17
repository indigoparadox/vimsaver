
import re
import subprocess
import collections
import logging
from vimsaver.multiplexers import Multiplexer

ScreenWinTuple = collections.namedtuple( 'ScreenWinTuple', ['idx', 'title'] )

class GNUScreen( Multiplexer ):

    @staticmethod
    def window_from_pty( pty_from : str ) -> int:

        logger = logging.getLogger( 'multiplexers.gnu_screen.window_from_pty' )

        pty_screen = re.match(
            r':\S*:S.(?P<screen>[0-9]*)', pty_from )
        if not pty_screen:
            return None

        window_num = int( pty_screen.group( 'screen' ) )

        logger.debug( 'PTY %s is screen: %d', pty_from, window_num )

        return window_num

    def __init__( self, session : str ):
        self.session = session

    def screen_command( self, window : int, command : list ):
        screenc = ['screen', '-S', self.session, '-X']
        if 0 <= window:
            screenc += ['-p', str( window )]
        screenc += command
        screenp = subprocess.run( screenc )

    def list_windows( self ):

        screenp = subprocess.Popen(
            ['screen', '-S', self.session, '-Q', 'windows'],
            stdout=subprocess.PIPE )

        lines_out = []
        word_idx = 0
        line = re.split( r'\s+', screenp.stdout.read().decode( 'utf-8' ) )
        prev_word = ''
        for word in line:

            if 0 == word_idx % 2:
                prev_word = word.strip( '*$' )
                prev_word = word.strip( '-' )
            else:
                lines_out.append( ScreenWinTuple( prev_word, word ) )
            
            word_idx += 1

        return lines_out

    def send_shell( self, command : list, window : int ):
        logger = logging.getLogger( 'multiplexers.gnu_screen.send_shell' )
        logger.debug( 'sending shell command: %s', str( command ) )
        command[-1] =  command[-1] + '^M'
        self.screen_command( window, ['stuff'] + command )

    def new_window( self, window : int ):
        logger = logging.getLogger( 'multiplexers.gnu_screen.new_window' )
        logger.debug( 'opening window %s in screen...', window )
        self.screen_command( -1, ['screen', window] )

MULTIPLEXER_CLASS = GNUScreen

