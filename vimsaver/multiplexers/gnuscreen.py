
import re
import subprocess
import collections
import logging
from vimsaver.multiplexers import Multiplexer, Window, PATTERN_PS, PS

ScreenWinTuple = collections.namedtuple( 'ScreenWinTuple', ['idx', 'title'] )

PATTERN_W = re.compile(
    r'\S*\s*(?P<tty>pts\/[0-9]*)\s*(?P<from>:pts\S*)\s*\S*\s*(?P<cli>.*)' )
PATTERN_PTS_SCREEN = re.compile( r':(?P<parent>\S*):S.(?P<screen>[0-9]*)' )
PATTERN_SCREEN_NUMBER = re.compile(
    r'(?P<idx>[0-9]*)\s*\((?P<title>[A-Za-z0-9]*)\)' )

class GNUScreen( Multiplexer ):

    def find_ps( self, command : str ) -> list:

        ''' Find all processes with "command" in their command line. '''

        logger = logging.getLogger( 'multiplexers.gnu_screen.find_ps' )

        psp = subprocess.Popen(
            ['ps', '-a', '-o', 'pid,tty,stat,args'],
            stdout=subprocess.PIPE )

        # Process raw ps command output.
        lines_out = []
        for line in psp.stdout.readlines():
            match = PATTERN_PS.match( line.decode( 'utf-8' ) )
            if not match:
                continue
            match = match.groupdict()

            if not command in match['cli']:
                continue

            yield PS( **match )

    def list_windows( self ) -> Window:

        logger = logging.getLogger( 'multiplexers.gnu_screen.list_windows' )

        wp = subprocess.Popen( ['w', '-s'], stdout=subprocess.PIPE )

        lines_out = []
        for line in wp.stdout.readlines():
            # TODO: Use re.match.
            match_w = PATTERN_W.match( line.decode( 'utf-8' ) )
            if not match_w:
                continue
            match_w = match_w.groupdict()

            logger.debug( 'line: %s', str( match_w ) )

            yield Window( multiplexer=self, index=int( line_arr[0] ), name=line_arr[1],
                pid=int( line_arr[2] ), tty=line_arr[3] )

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

        # Find the master proc belonging to screen.
        for sess_proc in self.find_ps( '-S ' + self.session ):
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

        subprocess.check_call(
            ['screen', '-S', self.session, '-p', idx, '-X', 'title', title],
            stdout=subprocess.PIPE )

    def send_shell( self, command : list, window : int ) -> None:
        logger = logging.getLogger( 'multiplexers.gnu_screen.send_shell' )
        logger.debug( 'sending shell command: %s', str( command ) )
        command[-1] =  command[-1] + '^M'
        self._screen_command( window, ['stuff'] + [' '.join( command )] )

    def new_window( self, idx : int ) -> None:
        logger = logging.getLogger( 'multiplexers.gnu_screen.new_window' )
        logger.debug( 'opening window %s in screen...', window )
        self._screen_command( -1, ['screen', window] )

MULTIPLEXER_CLASS = GNUScreen

