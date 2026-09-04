#!/usr/bin/env bash
# Funzioni condivise. Includi con:  source "$(dirname "$0")/lib/common.sh"
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }   # log su STDERR: non sporca lo stdout
die() { printf 'ERRORE: %s\n' "$*" >&2; exit "${2:-1}"; }    # muori con messaggio + exit code sensato
