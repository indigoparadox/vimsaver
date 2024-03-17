#!/usr/bin/env python3

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
import vimsaver.multiplexers
import vimsaver.psjobs as psjobs
from importlib import import_module

PATTERN_HISTORY = re.compile( r'\s*(?P<idx>[0-9]*)\s*(?P<cli>.*)' )

def screen_command( sessionname : str, window : int, command : list ):
    screenc = ['screen', '-S', sessionname, '-X']
    if 0 <= window:
        screenc += ['-p', str( window )]
    screenc += command
    screenp = subprocess.run( screenc )

def vim_command( servername : str, command : str ):
    vip = subprocess.run(
        ['vim', '--remote-send', command, '--servername', servername] )

def screen_build_list( **kwargs ):

    logger = logging.getLogger( 'list.screen' )

    multiplexer = import_module( kwargs['multiplexer'] ).MULTIPLEXER_CLASS()

    logger.debug( 'building screen list...' )

    screen_list = {}
    for pty in psjobs.list_pts():

        fg_proc =  None

        # TODO: Make sure pty is from screen with our session.

        # Build the vim buffer list.
        for ps in psjobs.list_ps_in_pty( pty['tty'] ):
            
            # TODO: Gracefully avoid other processes?
            #print( ps.cli )

            if -1 != ps['stat'].find( '+' ):
                fg_proc = ps

            # TODO: Skip or wait?
            if 'T' == ps['stat']:
                if fg_proc and -1 != fg_proc.cli[0].find( 'bash' ):
                    # Bring vim back to front!
                    logger.debug( 'resuming!' )
                    screen_command( session, pty.screen, ['stuff',
                        'fg^M'] )

                    # Start from the beginning to see if vim was brought
                    # forward.
                    # TODO: Can we get the job number to make sure it is?
                    raise vimsaver.TryAgainException()
                else:
                    logger.warning( 'don\'t know how to suspend: %s',
                        fg_proc )
                    raise vimsaver.SkipException()

            pty_screen = multiplexer.window_from_pty( pty['from'] )

            for app in kwargs['appstates']:
                if app.APPSTATE_CLASS.is_ps( ps ):
                    app_instance = app.APPSTATE_CLASS( ps, **kwargs )

                    buffers = app_instance.save_buffers()
                    #screen_list[pty_screen] = ps
                    screen_list[pty_screen] = {}
                    screen_list[pty_screen]['pwd'] = ps['pwd']
                    screen_list[pty_screen]['pty'] = dict( pty )
                    screen_list[pty_screen]['buffers'] = \
                        {app_instance.server_name: \
                            [dict( x._asdict() ) for x in buffers]}

    return screen_list

def do_save( **kwargs ):

    logger = logging.getLogger( 'save' )

    multiplexer = import_module( kwargs['multiplexer'] )

    #temp_dir = tempfile.mkdtemp( prefix='vimsaver' )
    #logger.debug( 'created temp dir: %s', temp_dir )
    done_trying = False
    screen_list = []
    while not done_trying:
        done_trying = True
        try:
            screen_list = screen_build_list( **kwargs )
        except vimsaver.TryAgainException:
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

    multiplexer = import_module( kwargs['multiplexer'] )

    # TODO: Make sure session doesn't exist!
    #screenp = subprocess.run( ['screen', '-d', '-m', '-S', kwargs['session']] )

    multiplexer_i = multiplexer.MULTIPLEXER_CLASS( kwargs['session'] )

    with open( kwargs['infile'], 'r' ) as infile_f:

        screen_state = json.loads( infile_f.read() )

        for screen in screen_state:
            pwd = screen_state[screen]['pwd']

            # Create window if missing.
            if screen not in [
            w.idx for w in multiplexer_i.list_windows()]:
                logger.debug( 'window %s not present yet...', screen )
                logger.debug( 'opening window %s in screen...', screen )
                screen_command( kwargs['session'], -1, ['screen', screen] )

            # Reopen vim buffers.
            # TODO: Only if not already open!
            for server in screen_state[screen]['buffers']:
                buffer_list = ' '.join(
                    [b['path'] for b in \
                        screen_state[screen]['buffers'][server]] )

                logger.debug( 'switching screen %s to cwd: %s', server, pwd )
                screen_command( kwargs['session'], int( screen ), ['stuff',
                    'cd {}^M'.format( pwd )] )

                logger.debug( 'opening buffers in screen %s vim: %s',
                    server, buffer_list )
                screen_command( kwargs['session'], int( screen ), ['stuff',
                    'vim --servername {} -p {}^M'.format(
                        server, buffer_list )] )

def do_quit( **kwargs ):

    logger = logging.getLogger( 'quit' )

    multiplexer = import_module( kwargs['multiplexer'] )

    for pty in psjobs.list_pts():

        fg_proc =  None

        # Build the vim buffer list.
        for ps in psjobs.list_ps_in_pty( pty.pty ):
            
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
                        raise vimsaver.TryAgainException()
                    else:
                        logger.warning( 'don\'t know how to suspend: %s',
                            fg_proc )
                        continue

                vim_server = ps.cli[2]

                vim_command( vim_server, '<Esc>:wqa<CR>' )

                raise vimsaver.TryAgainException()

            elif -1 != ps.cli[0].find( 'bash' ) and \
            -1 != ps.stat.find( '+' ):
                logger.debug( 'quitting screen: %s', pty.screen )
                screen_command( kwargs['session'],
                    int( pty.screen ), ['stuff', 'exit^M'] )

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument( '-v', '--verbose', action='store_true' )

    parser.add_argument( '-s', '--session', action='store', default='vimsave',
        help='Use this session name for vim and screen.' )

    parser.add_argument(
        '-m', '--multiplexer', action='store',
        default='vimsaver.multiplexers.gnuscreen' )

    parser.add_argument(
        '-a', '--appstates', action='append', type=import_module,
        default=[import_module( 'vimsaver.appstates.vim' )] )

    subparsers = parser.add_subparsers( required=True )

    parser_save = subparsers.add_parser( 'save' )

    parser_save.add_argument( '-b', '--bufferlist', default='BufferList',
        help='Name of vim user function to retrieve buffer list.' )

    parser_save.add_argument( '-o', '--outfile', default='vimsaver.json' )

    parser_save.set_defaults( func=do_save )

    parser_load = subparsers.add_parser( 'load' )

    parser_load.add_argument( '-i', '--infile', default='vimsaver.json' )

    parser_load.set_defaults( func=do_load )

    parser_quit = subparsers.add_parser( 'quit' )

    parser_quit.set_defaults( func=do_quit )

    args = parser.parse_args()

    print( args )

    log_level = logging.WARN
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig( level=log_level )
    logger = logging.getLogger( 'main' )

    args_arr = vars( args )
    args.func( **args_arr )

if '__main__' == __name__:
    main()

