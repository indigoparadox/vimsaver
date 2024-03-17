
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

def list_pts() -> list:

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

        lines_out.append( match )

    return lines_out

def list_ps_in_pty( pty : str ) -> list:

    ''' Return a named tuple containing a list of processes running in the
    given PTY. '''

    logger = logging.getLogger( 'list.ps' )

    psp = subprocess.Popen(
        ['ps', '-t', pty, '-o', 'pid,tty,stat,args'], stdout=subprocess.PIPE )

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
            match['pid'] = int( match['pid'] )
            match['cli'] = match['cli'].split( ' ' ) # TODO: Use re.split.
            match['pwd'] = \
                pwdp.stdout.read().decode( 'utf-8' ).split( ' ' )[1].strip()

            print( match )

            lines_out.append( match )
        except IndexError as e:
            logger.exception( e )

    return lines_out


