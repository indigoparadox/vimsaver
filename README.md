
# VIMSaver

A tool to preserve a set of screen tabs and vim buffers in vim sessions within those tabs.

## Setup

The following function is needed in the local .vimrc:

   function! BufferList()
      execute "silent redir @m"
      execute "silent buffers"
      execute "silent redir END"
      let a=@m
      return a
   endfunction

