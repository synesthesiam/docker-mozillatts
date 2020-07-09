FROM python:3.6 as build

ENV LANG C.UTF-8

# IFDEF PROXY
#! RUN echo 'Acquire::http { Proxy "http://${PROXY}"; };' >> /etc/apt/apt.conf.d/01proxy
RUN echo 'Acquire::http { Proxy "http://192.168.1.8:3142"; };' >> /etc/apt/apt.conf.d/01proxy
# ENDIF

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        espeak libsndfile1 git

RUN mkdir -p /app
RUN cd /app && \
    git clone https://github.com/mozilla/TTS && \
    cd TTS && \
    git checkout b1935c97

RUN cd /app/TTS && \
    python3 -m venv .venv

# IFDEF PYPI
#! ENV PIP_INDEX_URL=http://${PYPI}/simple/
#! ENV PIP_TRUSTED_HOST=${PYPI_HOST}
ENV PIP_INDEX_URL=http://192.168.1.8:4000/simple/
ENV PIP_TRUSTED_HOST=192.168.1.8
# ENDIF

RUN cd /app/TTS && \
    .venv/bin/pip3 install --upgrade pip && \
    .venv/bin/pip3 install -r requirements.txt && \
    .venv/bin/python3 setup.py install

# Extra packages missing from requirements
RUN cd /app/TTS && \
    .venv/bin/pip3 install inflect 'numba==0.48'

# Packages needed for web server
RUN cd /app/TTS && \
    .venv/bin/pip3 install 'flask' 'flask-cors'

# -----------------------------------------------------------------------------

FROM python:3.6-slim

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        espeak libsndfile1

COPY --from=build /app/TTS/.venv/ /app/
COPY vocoder/ /app/vocoder/
COPY model/ /app/model/
COPY templates/ /app/templates/
COPY tts.py scale_stats.npy /app/

WORKDIR /app

EXPOSE 5002

ENTRYPOINT ["/app/bin/python3", "/app/tts.py"]