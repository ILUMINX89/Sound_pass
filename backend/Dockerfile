FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
# Existing Windows checkouts can still have CRLF after pulling .gitattributes.
RUN sed -i 's/\r$//' src/recommendation/artifacts/model.json src/recommendation/artifacts/artist_profiles.json \
    && python -c "from src.recommendation.loader import load; load()"

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
