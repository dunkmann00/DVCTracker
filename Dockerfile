FROM python:3.9-slim

RUN apt-get clean && apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    locales gcc libpq-dev python3-dev git

# Set the locale
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

RUN python -m venv .venv
ENV PATH="/.venv/bin:$PATH"
RUN pip install --disable-pip-version-check pipenv==2023.2.18

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./Pipfile ./Pipfile.lock /usr/src/app/
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy
ENV PATH="/usr/src/app/.venv/bin:$PATH"


COPY ./ /usr/src/app

CMD ["gunicorn", "dvctracker:app", "--log-file", "-"]
