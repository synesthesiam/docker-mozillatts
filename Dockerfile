FROM python:3.7 as build

ENV LANG C.UTF-8

# IFDEF PROXY
#! RUN echo 'Acquire::http { Proxy "http://${APT_PROXY_HOST}:${APT_PROXY_PORT}"; };' >> /etc/apt/apt.conf.d/01proxy
# ENDIF

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        espeak libsndfile1 git

COPY source/ /source/

RUN mkdir -p /app && \
    cd /app && \
    if [ -f '/source/TTS.tar.gz' ]; then \
      tar -C /app -xf /source/TTS.tar.gz; \
    else \
      git clone https://github.com/mozilla/TTS; \
    fi

ENV VENV=/app/venv
RUN python3 -m venv ${VENV}

# IFDEF PROXY
#! ENV PIP_INDEX_URL=http://${PYPI_PROXY_HOST}:${PYPI_PROXY_PORT}/simple/
#! ENV PIP_TRUSTED_HOST=${PYPI_PROXY_HOST}
# ENDIF

# Set up Python virtual environment
RUN ${VENV}/bin/pip3 install --upgrade pip && \
    ${VENV}/bin/pip3 install --upgrade wheel setuptools

# Install torch from local cache if present
COPY download/ /download/

# IFDEF NOAVX
#! RUN mv download/noavx/* download/
# ENDIF

RUN ${VENV}/bin/pip3 install -f /download --no-index --no-deps 'torch==1.6.0' || true

# Install the rest of the requirements (excluding tensorflow)
RUN cd /app/TTS && \
    grep -v 'tensorflow' requirements.txt > requirements_notf.txt && \
    ${VENV}/bin/pip3 install -f /download -r requirements_notf.txt

# Install MozillaTTS itself
RUN cd /app/TTS && \
    mv requirements_notf.txt requirements.txt && \
    ${VENV}/bin/python3 setup.py install

# Packages needed for web server
RUN ${VENV}/bin/pip3 install -f download/ 'flask' 'flask-cors'

# -----------------------------------------------------------------------------

FROM python:3.7-slim

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        espeak \
        libsndfile1 libgomp1 libatlas3-base libgfortran4 libopenblas-base \
        libnuma1

COPY --from=build /app/venv/ /app/

ARG LANGUAGE=en
COPY model/${LANGUAGE}/ /app/model/
COPY tts_web/ /app/tts_web/
COPY run.sh /

WORKDIR /app

EXPOSE 5002

ENTRYPOINT ["/bin/bash", "/run.sh"]