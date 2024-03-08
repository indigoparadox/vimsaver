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
import time

PTYTuple = collections.namedtuple( 'PTYTuple', ['pty', 'parent', 'screen'] )
PSTuple = collections.namedtuple(
    'PSTuple', ['pid', 'pty', 'stat', 'cli', 'pwd'] )
VimTuple = collections.namedtuple(
    'VimTuple', ['idx', 'stat', 'insert', 'path', 'line'] )
ScreenWinTuple = collections.namedtuple( 'ScreenWinTuple', ['idx', 'title'] )

PATTERN_HISTORY = re.compile( r'\s*(?P<idx>[0-9]*)\s*(?P<cli>.*)' )
PATTERN_PS = re.compile(
    r'\s*(?P<pid>[0-9]+)\s*(?P<pty>[a-zA-Z0-9\/]+)\s*(?P<stat>\S+)\s*(?P<cli>.*)' )
PATTERN_BUFFERLIST = re.compile(
    r'\s*(?P<idx>[0-9]+)\s*(?P<stat>\S+)\s*(?P<insert>[+ ])\s*"(?P<path>.+)"\s*line (?P<line>[0-9]+)' )

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
        match = PATTERN_PS.match( line.decode( 'utf-8' ) )
        if not match:
            continue
        match = match.groupdict()

        try:
            # Get PWD.
            pwdp = subprocess.Popen(
                ['pwdx', match['pid']], stdout=subprocess.PIPE )
            pwd_out = pwdp.stdout.read().decode( 'utf-8' )

            lines_out.append(
                PSTuple(
                    int( match['pid'] ), match['pty'], match['stat'],
                    match['cli'].split( ' ' ),
                    pwd_out.split( ' ' )[1].strip() ) )
        except IndexError as e:
            logger.exception( e )

    return lines_out

def list_vi_buffers( servername : str, bufferlist_proc : str, show_h : bool = False ) -> list:

    vip = subprocess.Popen(
        ['vim', '--remote-expr', bufferlist_proc + '()',
            '--servername', servername],
        stdout=subprocess.PIPE )

    lines_out = []
    for line in vip.stdout.readlines():
        # TODO: Use re.match.
        match = PATTERN_BUFFERLIST.match( line.decode( 'utf-8' ) )
        if not match:
            continue
        match = match.groupdict()

        if 'h' == match['stat'] and not show_h:
            continue

        # Make index a number.
        match['idx'] = int( match['idx'] )

        # Account for buffer modes.
        if ' ' == match['insert']:
            # Vim is in insert mode?
            match['insert'] = '-'

        if '[No Name]' == match['path']:
            match['path'] = None

        lines_out.append( VimTuple( **match ) )

    return lines_out

def list_screen_windows( session : str ):

    screenp = subprocess.Popen(
        ['screen', '-Q', 'windows'], stdout=subprocess.PIPE )

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

def screen_command( sessionname : str, window : int, command : list ):
    screenc = ['screen', '-S', sessionname, '-X']
    if 0 <= window:
        screenc += ['-p', str( window )]
    screenc += command
    screenp = subprocess.run( screenc )

def screen_build_list( temp_dir : str, bufferlist : str, session : str ):

    logger = logging.getLogger( 'list.screen' )

    logger.debug( 'building screen list...' )

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
                        screen_command( session, pty.screen, ['stuff',
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

def do_save( **kwargs ):

    temp_dir = ''
    #temp_dir = tempfile.mkdtemp( prefix='vimsaver' )
    #logger.debug( 'created temp dir: %s', temp_dir )
    done_trying = False
    screen_list = []
    while not done_trying:
        done_trying = True
        try:
            screen_list = screen_build_list(
                temp_dir, kwargs['bufferlist'], kwargs['session'] )
        except TryAgainException:
            logger.debug( 'we should try again!' )
            done_trying = False
        finally:
            #logger.debug( 'removing temp dir: %s', temp_dir )
            #shutil.rmtree( temp_dir )
            pass

    #pprint.pprint( screen_list )

    with open( kwargs['outfile'], 'w' ) as outfile_f:
        outfile_f.write( json.dumps( screen_list ) )

def do_load( **kwargs ):

    logger = logging.getLogger( 'load' )

    # TODO: Make sure session doesn't exist!
    #screenp = subprocess.run( ['screen', '-d', '-m', '-S', kwargs['session']] )

    with open( kwargs['infile'], 'r' ) as infile_f:

        screen_state = json.loads( infile_f.read() )

        for screen in screen_state:
            pwd = screen_state[screen]['pwd']

            # Create window if missing.
            if screen not in [
            w.idx for w in list_screen_windows( kwargs['session'] )]:
                logger.debug( 'window %s not present yet...', screen )
                logger.debug( 'opening window %s in screen...', screen )
                screen_command( kwargs['session'], -1, ['screen', screen] )

            # Reopen vim buffers.
            for server in screen_state[screen]['buffers']:
                buffer_list = ' '.join(
                    [b['path'] for b in \
                        screen_state[screen]['buffers'][server]] )

                logger.debug( 'switching screen %s to cwd: %s', server, pwd )
                screen_command( kwargs['session'], int( screen ), ['stuff',
                    'cd {}^M'.format( pwd )] )

                #time.sleep( 1 )

                logger.debug( 'opening buffers in screen %s vim: %s',
                    server, buffer_list )
                screen_command( kwargs['session'], int( screen ), ['stuff',
                    'vim --servername {} -p {}^M'.format(
                        server, buffer_list )] )

                #time.sleep( 1 )


                #time.sleep( 1 )

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument( '-v', '--verbose', action='store_true' )

    parser.add_argument( '-s', '--session', action='store', default='vimsave',
        help='Use this session name for vim and screen.' )

    subparsers = parser.add_subparsers( required=True )

    parser_save = subparsers.add_parser( 'save' )

    parser_save.add_argument( '-b', '--bufferlist', default='BufferList',
        help='Name of vim user function to retrieve buffer list.' )

    parser_save.add_argument( '-o', '--outfile', default='vimsaver.json' )

    parser_save.set_defaults( func=do_save )

    parser_load = subparsers.add_parser( 'load' )

    parser_load.add_argument( '-i', '--infile', default='vimsaver.json' )

    parser_load.set_defaults( func=do_load )

    args = parser.parse_args()

    log_level = logging.WARN
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig( level=log_level )
    logger = logging.getLogger( 'main' )

    args_arr = vars( args )
    args.func( **args_arr )

if '__main__' == __name__:
    main()

