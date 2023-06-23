FROM python:3.10-slim-bullseye AS compile-image

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt --user && \
    pip list

FROM python:3.10-slim-bullseye AS runtime-image

COPY --from=compile-image /root/.local /root/.local
COPY --from=compile-image /etc/ssl /etc/ssl

WORKDIR /app

COPY run.py .
COPY astrolive astrolive

ENV PATH=/root/local/bin:$PATH

ENTRYPOINT ["python", "/app/run.py"]