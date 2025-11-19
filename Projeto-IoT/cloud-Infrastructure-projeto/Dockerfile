FROM debian:trixie-20231030

ENV PYTHONUNBUFFERED 1
ARG DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install jupyter python3-matplotlib python3-sklearn python3-pandas python3-pip --yes && apt clean

RUN pip install seaborn plotly --break-system-packages

# Set the display variable

ENV DISPLAY=:0

EXPOSE 8888

WORKDIR /

ADD startup.sh /startup.sh

ENV SHELL=/bin/bash

ENTRYPOINT ["/startup.sh"]

