FROM python:3.9-slim-buster

# RUN apk update && apk upgrade && \
#     apk add --no-cache make g++ bash git openssh postgresql-dev curl

RUN pip install pipenv

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./Pipfile ./Pipfile.lock /usr/src/app/
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy
ENV PATH="/.venv/bin:$PATH"

COPY ./ /usr/src/app

# EXPOSE 80

CMD ["gunicorn", "dvctracker:app", "--log-file", "-"]
