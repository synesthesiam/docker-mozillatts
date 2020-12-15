#!/usr/bin/env bash
set -e

url='localhost:5002/api/tts'
text='Welcome to the world of speech synthesis!'

# Test GET
curl -G --output - \
     --data-urlencode "text=${text}" "${url}" | \
    aplay

# Test POST
curl -X POST -H 'Content-Type: text/plain' --output - \
     --data "${text}" "${url}" | \
    aplay
