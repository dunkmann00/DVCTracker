FROM python:3.9

# RUN apk update && apk upgrade && \
#     apk add --no-cache make g++ bash git openssh postgresql-dev curl

RUN apt-get clean && apt-get -y update && \
    apt-get install -y locales

# Set the locale
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

RUN pip install --disable-pip-version-check pipenv==2023.2.18

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./Pipfile ./Pipfile.lock /usr/src/app/
RUN pipenv install --system --deploy

COPY ./ /usr/src/app

CMD ["gunicorn", "dvctracker:app", "--log-file", "-"]
