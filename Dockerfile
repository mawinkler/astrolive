FROM python:3.13.0b1-slim-bullseye AS compile-image

WORKDIR /app

ADD requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt --user && \
    pip list

FROM python:3.13.0b1-slim-bullseye AS runtime-image

COPY --from=compile-image /root/.local /root/.local
COPY --from=compile-image /etc/ssl /etc/ssl

WORKDIR /app

ADD run.py .
ADD astrolive astrolive

ENV PATH=/root/local/bin:$PATH

ENTRYPOINT ["python", "/app/run.py"]