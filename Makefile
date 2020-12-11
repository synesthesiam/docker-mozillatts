SHELL := bash

all:
	NOBUILDX=1 scripts/build-docker.sh

everything:
	for lang in en es fr de; do \
      export LANGUAGE=$$lang; \
      scripts/build-docker.sh; \
      if [[ $$lang -eq en ]]; then \
        NOAVX=1 scripts/build-docker.sh; \
      fi; \
    done
