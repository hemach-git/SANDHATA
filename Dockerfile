FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 sandhata
COPY --chown=sandhata:sandhata app.py ./
COPY --chown=sandhata:sandhata src ./src
COPY --chown=sandhata:sandhata .streamlit/config.toml ./.streamlit/config.toml
RUN mkdir -p /app/runtime/data && chown -R sandhata:sandhata /app/runtime /app/.streamlit
USER sandhata
EXPOSE 18501 18502
CMD ["python","-m","streamlit","run","app.py","--server.address=0.0.0.0","--server.port=18501"]
