#!/usr/bin/env bash
set -e

url='localhost:5002/process'
text='Welcome to the world of speech synthesis!'

# NOTE: Only INPUT_TEXT is actually used.

# Test GET
curl -G --output - \
     --data-urlencode "INPUT_TEXT=${text}" \
     --data-urlencode 'INPUT_TYPE=TEXT' \
     --data-urlencode 'OUTPUT_TYPE=AUDIO' \
     --data-urlencode 'LOCALE=en_US' \
     --data-urlencode 'AUDIO=WAVE_FILE' \
     --data-urlencode 'VOICE=cmu-slt-hsmm' \
     "${url}" | \
    aplay

# Test POST
curl -X POST -H 'Content-Type: text/plain' --output - \
     --data "INPUT_TEXT=${text}&INPUT_TYPE=TEXT&OUTPUT_TYPE=AUDIO&LOCALE=en_US&AUDIO=WAVE_FILE&VOICE=cmu-slt-hsmm" \
     "${url}" | \
    aplay
