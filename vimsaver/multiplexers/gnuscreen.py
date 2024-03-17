
import re
import subprocess
import collections
from vimsaver.multiplexers import Multiplexer

ScreenWinTuple = collections.namedtuple( 'ScreenWinTuple', ['idx', 'title'] )

class GNUScreen( Multiplexer ):

    @classmethod
    def window_from_pty( self, pty_from : str ):

        pty_screen = re.match(
            r':\S*:S.(?P<screen>[0-9]*)', pty_from )
        if not pty_screen:
            return None
        return pty_screen.group( 'screen' )

    def __init__( self, session : str ):
        self.session = session

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

MULTIPLEXER_CLASS = GNUScreen

