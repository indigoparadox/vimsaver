
import subprocess
import collections
import logging
from vimsaver.multiplexers import Multiplexer

class TMux( Multiplexer ):

    def __init__( self, session : str ):
        self.session = session

    def get_window_title( self, idx : int ) -> str:

        screenp = subprocess.Popen(
            ['tmux', 'display-message', '-t', f'{self.session}:{idx}', '-p', '#W'],
            stdout=subprocess.PIPE )

        return screenp.stdout.read().decode( 'utf-8' ).strip()

    def set_window_title( self, idx : int, title : str ) -> None:

        subprocess.check_call(
            ['tmux', 'rename-window', '-t', f'{self.session}:{idx}', title] )

    def send_shell( self, command : list, window : int ) -> None:

        subprocess.check_call(
            ['tmux', 'send-keys', '-t', f'{self.session}:{window}', ' '.join( command )] )
        subprocess.check_call(
            ['tmux', 'send-keys', '-t', f'{self.session}:{window}', 'Enter'] )

    def new_window( self, idx : int ) -> None:

        logger = logging.getLogger( 'multiplexers.tmux.new_window' )

        try:
            subprocess.check_call(
                ['tmux', 'new-window', '-t', f'{self.session}:{idx}'] )
        except subprocess.CalledProcessError as e:
            if 1 == e.returncode:
                logger.warning( 'window %d is already open!', idx )

MULTIPLEXER_CLASS = TMux
