SHELL := bash

.PHONY: everything reformat check

all:
	NOBUILDX=1 scripts/build-docker.sh

everything:
	@set -e; \
    for lang in en es fr de; do \
      export LANGUAGE=$$lang; \
      scripts/build-docker.sh; \
    done

reformat:
	scripts/format-code.sh

check:
	scripts/check-code.sh
