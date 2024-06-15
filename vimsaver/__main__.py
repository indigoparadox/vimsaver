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

def innerloop_save( screen_list, ps, pty, win_pty_idx, **kwargs ):

    logger = logging.getLogger( 'innerloop.save' )
    multiplexer = import_module( kwargs['multiplexer'] )
    multiplexer_i = multiplexer.MULTIPLEXER_CLASS( kwargs['session'] )

    for app_handler in kwargs['appstates']:

        if not app_handler.APPSTATE_CLASS.is_ps( ps ):
            continue

        pty.check_resume( ps, multiplexer_i, win_pty_idx )

        # Perform the save.
        app_instance = app_handler.APPSTATE_CLASS( ps, **kwargs )

        buffers = app_instance.save_buffers()
        screen_list[win_pty_idx] = {
            'pwd': ps.pwd,
            'app': app_instance.module_path,
            'title': app_instance.server_name,
            'buffers': {app_instance.server_name: \
                [dict( x._asdict() ) for x in buffers]}
        }

def innerloop_quit( screen_list, ps, pty, win_pty_idx, **kwargs ):

    logger = logging.getLogger( 'innerloop.quit' )
    multiplexer = import_module( kwargs['multiplexer'] )
    multiplexer_i = multiplexer.MULTIPLEXER_CLASS( kwargs['session'] )

    for app_handler in kwargs['appstates']:
        if not app_handler.APPSTATE_CLASS.is_ps( ps ):
            continue

        pty.check_resume( ps, multiplexer_i, win_pty_idx )

        # Perform the quit.
        app_instance = app_handler.APPSTATE_CLASS( ps, **kwargs )

        app_instance.quit()

    if not pty.fg_ps().has_cli( 'bash' ):
        logger.warning( 'don\'t know how to quit on: %s', pty.fg_is().cli[0] )
        raise vimsaver.SkipException()

    logger.debug( 'attempting to quit %s...', ps.cli[0] )
    multiplexer_i.send_shell( ['exit'], win_pty_idx )

def do_op( op_innerloop, **kwargs ):

    logger = logging.getLogger( 'save' )

    multiplexer = import_module( kwargs['multiplexer'] )
    multiplexer_i = multiplexer.MULTIPLEXER_CLASS( kwargs['session'] )

    #temp_dir = tempfile.mkdtemp( prefix='vimsaver' )
    #logger.debug( 'created temp dir: %s', temp_dir )
    done_trying = False
    while not done_trying:
        done_trying = True
        try:
            screen_list = {}
            for pty in psjobs.PTY.list_all():

                # Make sure pty is from screen with our session.
                win_pty_idx = multiplexer_i.window_from_pty( pty.parent )
                if 0 > win_pty_idx:
                    continue

                for ps in pty.list_ps():

                    # Build the vim buffer list.
                    try:
                        op_innerloop(
                            screen_list, ps, pty, win_pty_idx, **kwargs )
                    except vimsaver.SkipException:
                        continue

        except vimsaver.TryAgainException:
            logger.debug( 'we should try again!' )
            done_trying = False
        finally:
            #logger.debug( 'removing temp dir: %s', temp_dir )
            #shutil.rmtree( temp_dir )
            pass

    pprint.pprint( screen_list )

    if 'outfile' in kwargs:
        with open( kwargs['outfile'], 'w' ) as outfile_f:
            outfile_f.write( json.dumps( screen_list ) )

def do_load( op_func, **kwargs ):

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
            if not multiplexer_i.get_window_title( screen ):
                logger.debug( 'screen %s not found in window list', screen )
                multiplexer_i.new_window( screen )

            multiplexer_i.set_window_title(
                screen, screen_state[screen]['title'] )

            app = import_module( screen_state[screen]['app'] )

            # Reopen vim buffers.
            # TODO: Only if not already open!
            for server in screen_state[screen]['buffers']:

                app_i = app.APPSTATE_CLASS(
                    None, server_name=server, bufferlist=kwargs['bufferlist'] )

                if app_i.is_server_open():
                    logger.warning( '%s is already open...', server )
                    continue

                # Convert buffer list into command line.
                buffer_list = [b['path'] for b in \
                        screen_state[screen]['buffers'][server]]

                logger.debug(
                    'switching screen %s to pwd: %s', server, pwd )
                multiplexer_i.send_shell( ['cd', pwd], int( screen ) )

                logger.debug( 'opening buffers in screen %s vim: %s',
                    server, buffer_list )
                multiplexer_i.send_shell(
                    # TODO: Send shell command to start correct app.
                    ['vim', '--servername', server, '-p'] + buffer_list,
                    int( screen ) )

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument( '-v', '--verbose', action='store_true' )

    parser.add_argument( '-s', '--session', action='store', default='vimsaver',
        help='Use this session name for vim and screen.' )

    parser.add_argument(
        '-m', '--multiplexer', action='store',
        default='vimsaver.multiplexers.gnuscreen' )

    parser.add_argument(
        '-a', '--appstates', action='append', type=import_module,
        default=[import_module( 'vimsaver.appstates.vim' )] )

    parser.add_argument( '-b', '--bufferlist', default='BufferList',
        help='Name of vim user function to retrieve buffer list.' )

    subparsers = parser.add_subparsers( required=True )

    parser_save = subparsers.add_parser( 'save' )

    parser_save.add_argument( '-o', '--outfile', default='vimsaver.json' )

    parser_save.set_defaults( func=do_op, op=innerloop_save )

    parser_load = subparsers.add_parser( 'load' )

    parser_load.add_argument( '-i', '--infile', default='vimsaver.json' )

    parser_load.set_defaults( func=do_load, op=None )

    parser_quit = subparsers.add_parser( 'quit' )

    parser_quit.set_defaults( func=do_op, op=innerloop_quit )

    args = parser.parse_args()

    log_level = logging.WARN
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig( level=log_level )
    logger = logging.getLogger( 'main' )

    args_arr = vars( args )
    args.func( args.op, **args_arr )

if '__main__' == __name__:
    main()

