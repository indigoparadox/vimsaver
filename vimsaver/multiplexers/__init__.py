
class MultiplexerNotImplementedException( Exception ):
    pass

class Multiplexer( object ):

    def window_from_pty( self, pty_from : str ) -> int:
        raise MultiplexerNotImplementedException()

    def get_window_title( self, idx : int ):
        raise MultiplexerNotImplementedException()

    def set_window_title( self, idx : int, title : str ):
        raise MultiplexerNotImplementedException()

    def send_shell( self, command : list, window : int ):
        raise MultiplexerNotImplementedException()

    def new_window( self, window : int ):
        raise MultiplexerNotImplementedException()

