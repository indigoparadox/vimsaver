
import re
import logging
import subprocess
import collections

PATTERN_W = re.compile(
    r'\S*\s*(?P<tty>pts\/[0-9]*)\s*(?P<from>:pts\S*)\s*\S*\s*(?P<cli>.*)' )
PATTERN_PS = re.compile(
    r'\s*(?P<pid>[0-9]+)\s*(?P<pty>[a-zA-Z0-9\/]+)\s*(?P<stat>\S+)\s*(?P<cli>.*)' )
 
PSTuple = collections.namedtuple(
    'PSTuple', ['pid', 'pty', 'stat', 'cli', 'pwd'] )

class PTY( object ):

    @staticmethod
    def list_all() -> list:

        logger = logging.getLogger( 'list.pts' )

        wp = subprocess.Popen( ['w', '-s'], stdout=subprocess.PIPE )

        lines_out = []
        for line in wp.stdout.readlines():
            # TODO: Use re.match.
            match = PATTERN_W.match( line.decode( 'utf-8' ) )
            if not match:
                continue
            match = match.groupdict()

            logger.debug( 'line: %s', str( match ) )

            lines_out.append( PTY( **match ) )

        return lines_out

    def __init__( self, **kwargs ):
        self.name = kwargs['tty']
        self.parent = kwargs['from']

    def list_ps( self ) -> list:

        ''' Return a named tuple containing a list of processes running in the
        given PTY. '''

        logger = logging.getLogger( 'list.ps' )

        psp = subprocess.Popen(
            ['ps', '-t', self.name, '-o', 'pid,tty,stat,args'],
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
                match['pwd'] = \
                    pwdp.stdout.read().decode( 'utf-8' ).split( ' ' )[1].strip()

                lines_out.append( PS( **match ) )
            except IndexError as e:
                logger.exception( e )

        return lines_out

    def find_ps( self, command : str ):

        logger = logging.getLogger( 'pty.find_ps' )

        for ps in self.list_ps():
            print( ps )

        raise Exception()

    def fg_ps( self ):
        
        for ps in self.list_ps():
            
            # TODO: Gracefully avoid other processes?
            #print( ps.cli )

            if -1 != ps.stat.find( '+' ):
                return ps

        return None

class PS( object ):

    def __init__( self, **kwargs ):
        self.pid = int( kwargs['pid'] )
        self.cli = kwargs['cli'].split( ' ' ) # TODO: Use re.split.
        self.stat = kwargs['stat']
        self.pwd = kwargs['pwd']

    def is_suspended( self ):
        return 'T' == self.stat

    def has_cli( self, command : str ):
        return -1 != self.cli[0].find( command )

