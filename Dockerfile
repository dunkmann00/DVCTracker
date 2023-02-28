FROM python:3.9-slim AS base

RUN apt-get clean && apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    locales libpq-dev tmux

# Set the locale
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

ENV PYTHONUNBUFFERED=1

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

FROM base AS build

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gcc python3-dev git curl

# Install overmind
RUN mkdir -p /usr/src/app/overmind
RUN VERSION="v2.4.0" && \
    curl -Lso overmind/overmind.gz https://github.com/DarthSim/overmind/releases/download/$VERSION/overmind-$VERSION-linux-amd64.gz && \
    curl -Lso overmind/overmind.gz.sha256sum https://github.com/DarthSim/overmind/releases/download/$VERSION/overmind-$VERSION-linux-amd64.gz.sha256sum && \
    sha256sum overmind/overmind.gz | awk '{printf "%s",$1}' | cmp - overmind/overmind.gz.sha256sum && \
    gunzip -k overmind/overmind.gz && \
    chmod +x overmind/overmind

# Install pipenv
RUN python -m venv .pipenv-venv
ENV PATH="/usr/src/app/.pipenv-venv/bin:$PATH"
RUN pip install --disable-pip-version-check pipenv==2023.2.18

# Install projects python dependencies
COPY ./Pipfile ./Pipfile.lock /usr/src/app/
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base AS runtime

ENV PATH="/usr/src/app/.venv/bin:$PATH"
ENV GUNICORN_CMD_ARGS="--access-logfile -"

COPY --from=build /usr/src/app/.venv /usr/src/app/.venv
COPY --from=build /usr/src/app/overmind/overmind /usr/local/bin
COPY ./ /usr/src/app

CMD ["gunicorn", "dvctracker:app", "--log-file", "-"]
