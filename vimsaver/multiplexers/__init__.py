
from __future__ import annotations
import re
import logging
import subprocess
import collections
import vimsaver
import typing

class MultiplexerNotImplementedException( Exception ):
    pass

PATTERN_PS = re.compile(
    r'\s*(?P<pid>[0-9]+)\s*(?P<pty>[a-zA-Z0-9\/]+)\s*(?P<stat>\S+)\s*(?P<cli>.*)' )

class Multiplexer( object ):

    def list_windows( self ) -> typing.Generator[Window, None, None]:
        raise MultiplexerNotImplementedException()

    def window_from_pty( self, pty_from : str ) -> int:
        raise MultiplexerNotImplementedException()

    def get_window_count( self ) -> int:
        raise MultiplexerNotImplementedException()

    def get_window_title( self, idx : int ) -> str:
        raise MultiplexerNotImplementedException()

    def set_window_title( self, idx : int, title : str ) -> None:
        raise MultiplexerNotImplementedException()

    def send_shell( self, command : list, window : int ) -> None:
        raise MultiplexerNotImplementedException()

    def new_window( self, idx : int ) -> None:
        raise MultiplexerNotImplementedException()

class PS( object ):

    def __init__( self, **kwargs ):
        self.pid = int( kwargs['pid'] )
        self.pty = kwargs['pty']
        self.cli = kwargs['cli'].split( ' ' ) # TODO: Use re.split.
        self.stat = kwargs['stat']
        if 'pwd' in kwargs:
            self.pwd = kwargs['pwd']

    def is_suspended( self ):
        return 'T' == self.stat

    def has_cli( self, command : str ):
        return -1 != self.cli[0].find( command )

class Window( object ):

    def __init__(
        self, multiplexer : Multiplexer, name : str, pid : int, tty : str, index : int
    ):
        self.multiplexer = multiplexer
        self.name = name
        self.pid = pid
        self.tty = tty
        self.index = index

    def list_ps( self ) -> list:

        ''' Return a named tuple containing a list of processes running in the
        given PTY. '''

        logger = logging.getLogger( 'list.ps' )

        psp = subprocess.Popen(
            ['ps', '-t', self.tty, '-o', 'pid,tty,stat,args'],
            stdout=subprocess.PIPE )

        # Process raw ps command output.
        lines_out = []
        for line in psp.stdout.readlines():
            match = PATTERN_PS.match( line.decode( 'utf-8' ) )
            if not match:
                continue
            match = match.groupdict()

            try:
                # Get PWD.
                pwdp = subprocess.Popen(
                    ['pwdx', match['pid']], stdout=subprocess.PIPE )
                pwd_arr = pwdp.stdout.read().decode( 'utf-8' ).split( ' ' )
                #print( pwd_arr )
                match['pwd'] = pwd_arr[1].strip()

                lines_out.append( PS( **match ) )
            except IndexError as e:
                logger.exception( e )

        return lines_out

    def check_resume( self, ps : PS ):

        ''' Given a process, make sure it's in the foreground. '''

        logger = logging.getLogger( 'pty.check_resume' )

        if not ps.is_suspended():
            # Process is already in the foreground!
            return

        if not self.fg_ps().has_cli( 'bash' ):
            logger.warning(
                'don\'t know how to resume from: %s', self.fg_ps().cli[0] )
            raise vimsaver.SkipException()

        logger.debug( 'attempting to resume %s...', ps.cli[0] )
        # Bring vim back to front!
        self.multiplexer.send_shell( ['fg'], self.index )

        # Start from the beginning to see if vim was
        # brought forward.
        # TODO: Can we get the job number to make
        #       sure it is?
        raise vimsaver.TryAgainException()

    def fg_ps( self ):

        for ps in self.list_ps():

            # TODO: Gracefully avoid other processes?
            #print( ps.cli )

            if -1 != ps.stat.find( '+' ):
                return ps

        return None
