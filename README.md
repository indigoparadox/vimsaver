
# VIMSaver

A tool to preserve a set of screen tabs and vim buffers in vim sessions within those tabs.

## Setup

The following function is needed in the local .vimrc. The name of the function may be different, but it must then be specified with the -b option when running vimsaver.py.

 > function! BufferList()
 >
 >    execute "silent redir @m"
 >
 >    execute "silent buffers"
 >
 >    execute "silent redir END"
 >
 >    let a=@m
 >
 >    return a
 >
 > endfunction

## Usage

In order to be preserved, vim sessions must be opened with a --servername. You might add `alias vimsn="vim --servername"` to your .bash\_aliases file, so you can type "vimsn gridcity gridcity.c" to open a vim session called gridcity with the file gridcity.c to start. Any additional tabs you open with :tabnew should then be preserved.

Screen sessions to be preserved should also be opened with a session name. This will use the default session name, vimsaver: `screen -S vimsaver`.

In order to restore a session, open a screen with a session name and then simply run `./vimsaver.py load` (it will assume the default session name vimsaver, please see help for details).

