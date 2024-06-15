
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

    module_path = 'vimsaver.appstates.vim'

    def __init__( self, ps : vimsaver.psjobs.PS, **kwargs ):
        if ps:
            self.server_name = ps.cli[2]
        elif 'server_name' in kwargs:
            self.server_name = kwargs['server_name']

        self.bufferlist_proc = kwargs['bufferlist']

    @staticmethod
    def is_ps( ps : dict ):
        logger = logging.getLogger( 'appstate.vim.ps' )
        if 'vim' in ps.cli[0] and '--servername' == ps.cli[1]:
            logger.debug( 'found vim: "%s"', ps.cli[2] )
            return True
        return False

    def is_server_open( self ):
        
        try:
            vip = subprocess.run(
                ['vim', '--servername', self.server_name, '--remote-expr', '1'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=1 )

            output = vip.stdout.decode( 'utf-8' ).strip()
            if '1' == output:
                return True
        except subprocess.TimeoutExpired:
            # The servername must be active but asleep.
            return True

        return False

        raise Exception()

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

    def _vim_command( self, servername : str, command : str ):
        vip = subprocess.run(
            ['vim', '--remote-send', command, '--servername', servername] )

    def quit( self ):
        self._vim_command( self.server_name, '<Esc>:wqa<CR>' )

APPSTATE_CLASS = VimState

