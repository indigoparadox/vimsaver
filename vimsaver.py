#!/usr/bin/env python3

import psutil
import subprocess
import re
import collections
import json

PTYTuple = collections.namedtuple( 'PTYTuple', ['pty', 'parent', 'screen'] )
PSTuple = collections.namedtuple( 'PSTuple', ['pid', 'pty', 'cli', 'pwd'] )
VimTuple = collections.namedtuple( 'VimTuple', ['idx', 'state', 'path'] )

def list_pts() -> list:
    wp = subprocess.Popen( ['w'], stdout=subprocess.PIPE )

    lines_out = []
    for line in wp.stdout.readlines():
        line = re.split( r'\s+', line.decode( 'utf-8' ) )
        if 3 > len( line ) or not line[2].startswith( ':pts' ):
            continue

        # Place the PTY running inside first, then the parent and screen socket.
        ps_line = [line[1]]
        ps_line += line[2].split( ':' )[1:]

        lines_out.append( PTYTuple( *ps_line ) )

    return lines_out

def list_ps_in_pty( pty : str ) -> list:

    ''' Return a named tuple containing a list of processes running in the
    given PTY. '''

    psp = subprocess.Popen(
        ['ps', '-t', pty, '-o', 'pid,tty,args'], stdout=subprocess.PIPE )

    # Process raw ps command output.
    lines_out = []
    for line in psp.stdout.readlines():
        line = re.split( r'\s+', line.decode( 'utf-8' ) )[1:-1]

        # Weed out headers and empty columns.
        if 'PID' == line[0]:
            continue
        assert( line[1] == pty )
        assert( line[0].isnumeric() )

        # Get PWD.
        pwdp = subprocess.Popen( ['pwdx', line[0]], stdout=subprocess.PIPE )

        lines_out.append( PSTuple( int( line[0] ), line[1], line[2:],
            pwdp.stdout.read().decode( 'utf-8' ).split( ' ' )[1].strip() ) )

    return lines_out

def list_vi_buffers( servername : str ) -> list:

    vip = subprocess.Popen(
        ['vim', '--remote-expr', 'BufferList()', '--servername', servername],
        stdout=subprocess.PIPE )

    lines_out = []
    for line in vip.stdout.readlines():
        line = [x.strip( '"' ) for x in \
            re.split( r'\s+', line.decode( 'utf-8' ) )[1:-3]]

        if 0 == len( line ):
            continue

        assert( line[0].isnumeric() )
        line[0] = int( line[0] )

        lines_out.append( VimTuple( *line ) )

    return lines_out

def build_screen_list():

    screen_list = {}
    for pty in list_pts():
        ps_list = []
        for ps in list_ps_in_pty( pty.pty ):
            if 'vim' in ps.cli[0] and '--servername' == ps.cli[1]:
                vim_server = ps.cli[2]
                screen_list[vim_server] = dict( ps._asdict() )
                screen_list[vim_server]['buffers'] = \
                    [dict( x._asdict() ) for x in list_vi_buffers( vim_server )]

    return screen_list

def main():

    screen_list = build_screen_list()
    print( json.dumps( screen_list ) )

if '__main__' == __name__:
    main()

