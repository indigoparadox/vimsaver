
# VIMSaver

A tool to preserve a set of screen tabs and vim buffers in vim sessions within those tabs.

## Setup

The following function is needed in the local .vimrc. The name of the function may be different, but it must then be specified with the -b option when running vimsaver.py.

   function! BufferList()
      execute "silent redir @m"
      execute "silent buffers"
      execute "silent redir END"
      let a=@m
      return a
   endfunction

