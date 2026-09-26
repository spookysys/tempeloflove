#!/bin/sh
# Preview quality: 480x270 films (about 1-2 h each on 4 CPU cores) and quick stills.
exec "$(dirname "$0")/render.sh" lq "$@"
