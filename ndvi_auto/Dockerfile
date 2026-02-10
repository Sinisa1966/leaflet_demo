FROM python:3.13-slim

WORKDIR /app

# Instaliraj sistemske biblioteke potrebne za rasterio i shapely
RUN apt-get update && apt-get install -y \
    libexpat1 \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Instaliraj potrebne biblioteke
RUN pip install --no-cache-dir \
    rasterio \
    shapely \
    numpy \
    requests \
    pyproj

# Kopiraj sve Python skripte
COPY *.py /app/
# Kopiraj GeoJSON i SLD fajlove
COPY . /app/

# Kreiraj data direktorijum
RUN mkdir -p /app/data

# Default komanda - može se override-ovati u docker-compose.yml
CMD ["python", "/app/run_loop.py"]
