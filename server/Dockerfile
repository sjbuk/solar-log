FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY solarlog_server ./solarlog_server
RUN pip install --no-cache-dir .
ENV SOLARLOG_DB=/data/solarlog.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "solarlog_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
