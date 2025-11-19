
import re
import subprocess
import collections
import logging
from vimsaver.multiplexers import Multiplexer
from vimsaver.multiplexers import PTY

ScreenWinTuple = collections.namedtuple( 'ScreenWinTuple', ['idx', 'title'] )

PATTERN_W = re.compile(
    r'\S*\s*(?P<tty>pts\/[0-9]*)\s*(?P<from>:pts\S*)\s*\S*\s*(?P<cli>.*)' )
PATTERN_PTS_SCREEN = re.compile( r':(?P<parent>\S*):S.(?P<screen>[0-9]*)' )
PATTERN_SCREEN_NUMBER = re.compile(
    r'(?P<idx>[0-9]*)\s*\((?P<title>[A-Za-z0-9]*)\)' )

class GNUScreen( Multiplexer ):

    def list_windows( self ) -> PTY:

        logger = logging.getLogger( 'multiplexers.gnu_screen.list_pts' )

        wp = subprocess.Popen( ['w', '-s'], stdout=subprocess.PIPE )

        lines_out = []
        for line in wp.stdout.readlines():
            # TODO: Use re.match.
            match = PATTERN_W.match( line.decode( 'utf-8' ) )
            if not match:
                continue
            match = match.groupdict()

            logger.debug( 'line: %s', str( match ) )

            yield PTY( **match )

    def window_from_pty( self, pty_from : str ) -> int:

        logger = logging.getLogger( 'multiplexers.gnu_screen.window_from_pty' )

        pty_screen = PATTERN_PTS_SCREEN.match( pty_from )

        # Weed out screens with other session names.
        if pty_screen['parent'] != self.session_pty:
            logger.debug( '%s not in screen %s', pty_from, self.session_pty )
            return -1

        if not pty_screen:
            logger.debug( 'no match found for ' + pty_from )
            return -1

        window_num = int( pty_screen.group( 'screen' ) )

        logger.debug( 'PTY %s is window: %d', pty_from, window_num )

        return window_num

    def __init__( self, session : str ):
        self.session = session
        self.session_pty = None

        # Find the master proc.
        for sess_proc in psjobs.PTY.find_ps( '-S ' + self.session ):
            assert( None == self.session_pty ) # Only one!
            self.session_pty = sess_proc.pty

        if None == self.session_pty:
            raise Exception( "Could not find screen for session: " + session + \
                " was it resumed without -S?" )

    def _screen_command( self, window : int, command : list ):
        logger = logging.getLogger( 'multiplexers.gnu_screen.command' )
        screenc = ['screen', '-S', self.session, '-X']
        if 0 <= window:
            screenc += ['-p', str( window )]
        screenc += command
        logger.debug( screenc )
        screenp = subprocess.run( screenc )

    def get_window_title( self, idx : int ) -> str:

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

    def set_window_title( self, idx : int, title : str ) -> None:

        screenp = subprocess.Popen(
            ['screen', '-S', self.session, '-p', idx, '-X', 'title', title],
            stdout=subprocess.PIPE )

    def send_shell( self, command : list, window : int ) -> None:
        logger = logging.getLogger( 'multiplexers.gnu_screen.send_shell' )
        logger.debug( 'sending shell command: %s', str( command ) )
        command[-1] =  command[-1] + '^M'
        self._screen_command( window, ['stuff'] + [' '.join( command )] )

    def new_window( self, window : int ) -> None:
        logger = logging.getLogger( 'multiplexers.gnu_screen.new_window' )
        logger.debug( 'opening window %s in screen...', window )
        self._screen_command( -1, ['screen', window] )

MULTIPLEXER_CLASS = GNUScreen

