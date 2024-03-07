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

PTYTuple = collections.namedtuple( 'PTYTuple', ['pty', 'parent', 'screen'] )
PSTuple = collections.namedtuple(
    'PSTuple', ['pid', 'pty', 'stat', 'cli', 'pwd'] )
VimTuple = collections.namedtuple(
    'VimTuple', ['idx', 'state', 'insert', 'path'] )

PATTERN_HISTORY = re.compile( r'\s*(?P<idx>[0-9]*)\s*(?P<cli>.*)' )

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

        # Get PWD.
        pwdp = subprocess.Popen( ['pwdx', line[0]], stdout=subprocess.PIPE )

        lines_out.append( PSTuple( int( line[0] ), line[1], line[2], line[3:],
            pwdp.stdout.read().decode( 'utf-8' ).split( ' ' )[1].strip() ) )

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

def vim_command( servername : str, command : str ):
    vimc = ['vim', '--servername', servername, '--remote-send', command]
    vimp = psutil.Popen( vimc )

def screen_command( sessionname : str, window : int, command : list ):
    screenc = ['screen', '-S', sessionname, '-X', '-p', str( window )] + command
    screenp = psutil.Popen( screenc )

def screen_build_list( temp_dir : str, bufferlist : str ):
    screen_list = {}
    for pty in list_pts():
        temp_hist = os.path.join( temp_dir, pty.pty.replace( '/', '_' ) )
        vim_is_present = False
        vim_is_in_insert = False
        # Build the vim buffer list.
        for ps in list_ps_in_pty( pty.pty ):
            
            # TODO: Gracefully avoid other processes?
            #print( ps.cli )
            #assert( 'vim' in ps.cli or 'bash' in ps.cli )

            if 'vim' in ps.cli[0] and '--servername' == ps.cli[1]:
                # We only care about *named* vim sessions.

                vim_is_present = True
                if 'T' == ps.stat:
                    # Bring vim back to front!
                    screen_command( 'vimsaver', pty.screen, ['stuff', 'fg^M'] )

                vim_server = ps.cli[2]
                vim_buffers = list_vi_buffers( vim_server, bufferlist )

                # Determine buffer insert status for later.
                for buf in vim_buffers:
                    print( buf )
                    if '+' == buf.insert:
                        print( vim_server + ' is in insert' )
                        #vim_is_in_insert = True
                        vim_command( vim_server, '<Esc>' )

                # Add vim buffers to list.
                screen_list[pty.screen] = dict( ps._asdict() )
                screen_list[pty.screen]['pty'] = dict( pty._asdict() )
                screen_list[pty.screen]['buffers'] = \
                    {vim_server: [dict( x._asdict() ) for x in vim_buffers]}

        # TODO: Handle vim being in insert.
        assert( not vim_is_in_insert )
        assert( vim_is_present )

        if vim_is_present:
            # Suspend foreground, grab bash history, resume foreground.
            #if vim_is_in_insert:
            #    screen_command( 'vimsaver', pty.screen, ['stuff', '^C'] )
            screen_command( 'vimsaver', pty.screen, ['stuff', '^Z'] )

            # TODO: Check if bash is in foreground before executing this.
            screen_command( 'vimsaver', pty.screen,
                ['stuff', ' history > ' + temp_hist + '^M'] )

            screen_command( 'vimsaver', pty.screen, ['stuff', 'fg^M'] )

        with open( temp_hist, 'r' ) as temp_hist_f:
            screen_list[pty.screen]['history'] = []
            for line in temp_hist_f.readlines():
                match = PATTERN_HISTORY.match( line )
                #print( match.groupdict() )
                screen_list[pty.screen]['history'].append( match.groupdict() )

    return screen_list

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument( '-b', '--bufferlist', default='BufferList',
        help='Name of vim user function to retrieve buffer list.' )

    args = parser.parse_args()

    temp_dir = tempfile.mkdtemp( prefix='vimsaver' )
    try:
        screen_list = screen_build_list( temp_dir, args.bufferlist )
    finally:
        shutil.rmtree( temp_dir )

    pprint.pprint( screen_list )

if '__main__' == __name__:
    main()

