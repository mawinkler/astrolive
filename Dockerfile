FROM python:3.10.0-slim-bullseye

RUN mkdir -p /usr/src/app/astrolive

ADD run.py /usr/src/app
ADD requirements.txt /usr/src/app
ADD astrolive /usr/src/app/astrolive

WORKDIR /usr/src/app

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python", "./run.py"]