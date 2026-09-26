#!/bin/sh
# Full quality: 1920x1080 films at 64 samples, every frame (days on a CPU; use a GPU box), full stills.
exec "$(dirname "$0")/render.sh" hq "$@"
