ARG PYTHON_IMAGE=python:3.12.10-slim
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip check
COPY app.py .
USER 10001:10001
EXPOSE 8080
CMD ["python", "app.py"]
