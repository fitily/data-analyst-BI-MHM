FROM python:3.10-slim
WORKDIR /usr/app
RUN apt-get update && apt-get install -y gcc git default-libmysqlclient-dev && rm -rf /var/lib/apt-get/lists/*
RUN pip install --no-cache-dir "dbt-core==1.7.0" "dbt-mysql==1.7.0" "protobuf<4.25.0"
