SHELL := bash

all:
	NOBUILDX=1 scripts/build-docker.sh

everything:
	@set -e; \
    for lang in en es fr de; do \
      export LANGUAGE=$$lang; \
      scripts/build-docker.sh; \
      if [[ $$lang -eq en ]]; then \
        NOAVX=1 PLATFORMS=linux/amd64 scripts/build-docker.sh; \
      fi; \
    done
