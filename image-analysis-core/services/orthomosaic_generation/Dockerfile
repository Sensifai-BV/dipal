# Use Ubuntu 24.04 as the base image for modern dependency versions
FROM ubuntu:24.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install Build Dependencies
# These correspond to the "Prerequisites" and dependent libraries mentioned in the docs.
# - build-essential: GCC/G++ compilers and make
# - cmake: Required build system
# - git: To clone the repository
# - libgdal-dev: Required for GDAL support (raster/vector I/O)
# - libgeotiff-dev: Required for GeoTIFF support
# - liblaszip-dev: Highly recommended for compressed LAS support
# - libzstd-dev: Compression support
# - libxml2-dev: XML parsing support
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libproj-dev \
    libgeotiff-dev \
    liblaszip-dev \
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

# 2. Get the Source Code
# We clone the specific version tag (2.9.2) as requested.
WORKDIR /usr/local/src
RUN git clone --depth 1 --branch 2.9.2 https://github.com/PDAL/PDAL.git pdal

# 3. Configure, Build, and Install
# We create a build directory, run CMake to generate Makefiles, and then compile.
WORKDIR /usr/local/src/pdal/build

# CMake Options:
# - DCMAKE_BUILD_TYPE=Release: Optimizes the build for performance
# - DCMAKE_INSTALL_PREFIX=/usr/local: Standard install location
# - DPDAL_BUILD_PLUGINS=ON: Builds standard plugins enabled by default
RUN cmake .. \
    -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    && make -j$(nproc) \
    && make install

# 4. Verification
# Clean up build artifacts to keep image smaller (optional) and verify installation
WORKDIR /
RUN rm -rf /usr/local/src/pdal

WORKDIR /app
COPY services/orthomosaic_generation/requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY infrastructure/ ./infrastructure/
COPY shared/ ./shared/
COPY services/orthomosaic_generation/ ./services/orthomosaic_generation/

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"ORTHOMOSAIC_SERVICE_PORT\",8003)}/health/')"

# Show the installed version to verify success
CMD ["pdal", "--version"]

