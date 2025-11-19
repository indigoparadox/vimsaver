
class MultiplexerNotImplementedException( Exception ):
    pass

class Multiplexer( object ):

    def window_from_pty( self, pty_from : str ) -> int:
        raise MultiplexerNotImplementedException()

    def get_window_count( self ) -> int:
        raise MultiplexerNotImplementedException()

    def get_window_title( self, idx : int ) -> str:
        raise MultiplexerNotImplementedException()

    def set_window_title( self, idx : int, title : str ) -> None:
        raise MultiplexerNotImplementedException()

    def send_shell( self, command : list, window : int ) -> None:
        raise MultiplexerNotImplementedException()

    def new_window( self, idx : int ) -> None:
        raise MultiplexerNotImplementedException()

