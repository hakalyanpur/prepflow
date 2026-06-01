FROM python:3.11-slim

WORKDIR /app

COPY tracker.py .
COPY plan.json .
COPY python_ref.json .
COPY python_mechanics.json .
COPY patterns.md .
COPY java_ref.json .
COPY tips.json .

ENV HOST=0.0.0.0
ENV PORT=8080
ENV DATA_DIR=/data

EXPOSE 8080

CMD ["python3", "tracker.py", "--no-open"]
