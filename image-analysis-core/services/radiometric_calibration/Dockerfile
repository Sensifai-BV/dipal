FROM ubuntu:24.04


# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libproj-dev \
    libgeotiff-dev \
    libzstd-dev \
    libxml2-dev \
    libsqlite3-dev \
    libtiff-dev \
    libjpeg-dev \
    libpng-dev \
    libexpat-dev \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Build GDAL from source
WORKDIR /usr/local/src
RUN git clone --depth 1 --branch v3.12.2 https://github.com/OSGeo/gdal.git gdal \
    && cd gdal \
    && mkdir build \
    && cd build \
    && cmake .. \
        -G "Unix Makefiles" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_SHARED_LIBS=ON \
        -DGDAL_BUILD_OPTIONAL_DRIVERS=ON \
        -DOGR_BUILD_OPTIONAL_DRIVERS=ON \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && cd /usr/local/src \
    && rm -rf gdal

WORKDIR /app

COPY services/radiometric_calibration/requirements.txt .

RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY infrastructure/ ./infrastructure/
COPY shared/ ./shared/
COPY services/radiometric_calibration/ ./services/radiometric_calibration/

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"CALIBRATION_SERVICE_PORT\",8001)}/health/')"
