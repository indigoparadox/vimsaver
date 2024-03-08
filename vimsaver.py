#!/usr/bin/env python3

import psutil
import subprocess
import re
import collections
import json
import argparse
import pprint
import tempfile
import os
import shutil
import logging

PTYTuple = collections.namedtuple( 'PTYTuple', ['pty', 'parent', 'screen'] )
PSTuple = collections.namedtuple(
    'PSTuple', ['pid', 'pty', 'stat', 'cli', 'pwd'] )
VimTuple = collections.namedtuple(
    'VimTuple', ['idx', 'state', 'insert', 'path'] )

PATTERN_HISTORY = re.compile( r'\s*(?P<idx>[0-9]*)\s*(?P<cli>.*)' )

class TryAgainException( Exception ):
    pass

def list_pts() -> list:
    wp = subprocess.Popen( ['w'], stdout=subprocess.PIPE )

    lines_out = []
    for line in wp.stdout.readlines():
        # TODO: Use re.match.
        line = re.split( r'\s+', line.decode( 'utf-8' ) )
        if 3 > len( line ) or not line[2].startswith( ':pts' ):
            continue

        # Place the PTY running inside first, then the parent and screen socket.
        pty_line = [line[1]]
        pty_line += line[2].split( ':' )[1:]
        pty_line[2] = int( pty_line[2].strip( 'S.' ) )

        lines_out.append( PTYTuple( *pty_line ) )

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
        # TODO: Use re.match.
        line = re.split( r'\s+', line.decode( 'utf-8' ) )[1:-1]

        # Weed out headers and empty columns.
        if 'PID' == line[0]:
            continue
        assert( line[1] == pty )
        assert( line[0].isnumeric() )

        try:
            # Get PWD.
            pwdp = subprocess.Popen( ['pwdx', line[0]], stdout=subprocess.PIPE )

            lines_out.append(
                PSTuple( int( line[0] ), line[1], line[2], line[3:],
                pwdp.stdout.read().decode( 'utf-8' ).split( ' ' )[1].strip() ) )
        except IndexError as e:
            logger.exception( e )
        

    return lines_out

def list_vi_buffers( servername : str, bufferlist_proc : str ) -> list:

    vip = subprocess.Popen(
        ['vim', '--remote-expr', bufferlist_proc + '()',
            '--servername', servername],
        stdout=subprocess.PIPE )

    lines_out = []
    for line in vip.stdout.readlines():
        # TODO: Use re.match.
        line = [x.strip( '"' ) for x in \
            re.split( r'\s+', line.decode( 'utf-8' ) )[1:-3]]

        if 0 == len( line ):
            continue

        # Make index a number.
        assert( line[0].isnumeric() )
        line[0] = int( line[0] )

        # Account for buffer modes.
        if len( line ) == 2:
            line.insert( 1, '' )
        if len( line ) == 3:
            # Vim is in insert mode?
            line.insert( 2, '-' )

        lines_out.append( VimTuple( *line ) )

    return lines_out

# vim -servername x -p f1 f2
# screen -S vimsaver -X screen
# screen -S vimsaver -X stuff 'history -r xxx'

def screen_command( sessionname : str, window : int, command : list ):
    screenc = ['screen', '-S', sessionname, '-X', '-p', str( window )] + command
    screenp = psutil.Popen( screenc )

def screen_build_list( temp_dir : str, bufferlist : str ):

    logger = logging.getLogger( 'list.screen' )

    screen_list = {}
    for pty in list_pts():

        fg_proc =  None

        # Build the vim buffer list.
        for ps in list_ps_in_pty( pty.pty ):
            
            # TODO: Gracefully avoid other processes?
            #print( ps.cli )

            if -1 != ps.stat.find( '+' ):
                fg_proc = ps

            if 'vim' in ps.cli[0] and '--servername' == ps.cli[1]:
                # We only care about *named* vim sessions.
                logger.debug( 'found vim "%s"', ps.cli[2] )

                # TODO: Skip or wait?
                if 'T' == ps.stat:
                    if fg_proc and -1 != fg_proc.cli[0].find( 'bash' ):
                        # Bring vim back to front!
                        logger.debug( 'resuming!' )
                        screen_command( 'vimsaver', pty.screen, ['stuff',
                            'fg^M'] )

                        # Start from the beginning to see if vim was brought
                        # forward.
                        # TODO: Can we get the job number to make sure it is?
                        raise TryAgainException()
                    else:
                        logger.warning( 'don\'t know how to suspend: %s',
                            fg_proc )
                        continue

                vim_server = ps.cli[2]
                vim_buffers = list_vi_buffers( vim_server, bufferlist )

                # Add vim buffers to list.
                screen_list[pty.screen] = dict( ps._asdict() )
                screen_list[pty.screen]['pty'] = dict( pty._asdict() )
                screen_list[pty.screen]['buffers'] = \
                    {vim_server: [dict( x._asdict() ) for x in vim_buffers]}

    return screen_list

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument( '-b', '--bufferlist', default='BufferList',
        help='Name of vim user function to retrieve buffer list.' )

    parser.add_argument( '-v', '--verbose', action='store_true' )

    parser.add_argument( '-o', '--out', default='vimsaver.json' )

    args = parser.parse_args()

    log_level = logging.WARN
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig( level=log_level )
    logger = logging.getLogger( 'main' )

    temp_dir = ''
    #temp_dir = tempfile.mkdtemp( prefix='vimsaver' )
    #logger.debug( 'created temp dir: %s', temp_dir )
    done_trying = False
    while not done_trying:
        done_trying = True
        try:
            screen_list = screen_build_list( temp_dir, args.bufferlist )
        except TryAgainException:
            logger.debug( 'we should try again!' )
            done_trying = False
        finally:
            #logger.debug( 'removing temp dir: %s', temp_dir )
            #shutil.rmtree( temp_dir )
            pass

    #pprint.pprint( screen_list )

    with open( args.out, 'w' ) as out_f:
        out_f.write( json.dumps( screen_list ) )

if '__main__' == __name__:
    main()

