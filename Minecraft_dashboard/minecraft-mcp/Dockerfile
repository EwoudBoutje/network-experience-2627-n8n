FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastmcp>=2.12,<3" \
    "rcon==2.3.8"

COPY server.py .

USER 10001:10001

CMD ["python", "server.py"]
