
import logging
import re
import collections
import vimsaver
import subprocess
from vimsaver.appstates import AppState

PATTERN_BUFFERLIST = re.compile(
    r'\s*(?P<idx>[0-9]+)\s*(?P<stat>\S+)\s*(?P<insert>[+ ])\s*"(?P<path>.+)"\s*line (?P<line>[0-9]+)' )

VimTuple = collections.namedtuple(
    'VimTuple', ['idx', 'stat', 'insert', 'path', 'line'] )

class VimState( AppState ):

    def __init__( self, ps, **kwargs ):
        self.server_name = ps['cli'][2]
        self.bufferlist_proc = kwargs['bufferlist']

    @classmethod
    def is_ps( self, ps : dict ):
        logger = logging.getLogger( 'appstate.vim.ps' )
        if 'vim' in ps['cli'][0] and '--servername' == ps['cli'][1]:
            logger.debug( 'found vim: "%s"', ps['cli'][2] )
            return True
        return False

    def save_buffers( self ):

        logger = logging.getLogger( 'appstate.vim.save' )

        # We only care about *named* vim sessions.
        logger.debug( 'found vim "%s"', self.server_name )

        vip = subprocess.Popen(
            ['vim', '--remote-expr', self.bufferlist_proc + '()',
                '--servername', self.server_name],
            stdout=subprocess.PIPE )

        # Add vim buffers to list.
        lines_out = []
        for line in vip.stdout.readlines():
            match = PATTERN_BUFFERLIST.match( line.decode( 'utf-8' ) )
            if not match:
                continue
            match = match.groupdict()

            if 'h' == match['stat']:
                # Skip hidden buffers.
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

APPSTATE_CLASS = VimState

