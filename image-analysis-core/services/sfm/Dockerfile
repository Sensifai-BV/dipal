ARG UBUNTU_VERSION=24.04
ARG NVIDIA_CUDA_VERSION=12.9.1

#
# Docker builder stage.
#
FROM nvidia/cuda:${NVIDIA_CUDA_VERSION}-devel-ubuntu${UBUNTU_VERSION} AS builder

ARG COLMAP_GIT_COMMIT=3.13.0
ARG CUDA_ARCHITECTURES=all-major
# Pin Ceres version for stability
ARG CERES_VERSION=2.2.0
ENV QT_XCB_GL_INTEGRATION=xcb_egl

# Prevent stop building ubuntu at time zone selection.
ENV DEBIAN_FRONTEND=noninteractive

# Prepare and empty machine for building.
# Removed libceres-dev.
# Added libsuitesparse-dev, libgflags-dev.
RUN apt-get update && \
    apt-get install -y \
        git \
        cmake \
        ninja-build \
        build-essential \
        libboost-program-options-dev \
        libboost-graph-dev \
        libboost-system-dev \
        libeigen3-dev \
        libfreeimage-dev \
        libmetis-dev \
        libgoogle-glog-dev \
        libgflags-dev \
        libsuitesparse-dev \
        libgtest-dev \
        libgmock-dev \
        libsqlite3-dev \
        libglew-dev \
        qt6-base-dev \
        libqt6opengl6-dev \
        libqt6openglwidgets6 \
        libcgal-dev \
        libssl-dev \
        libmkl-full-dev \
        libflann-dev

# Build and install Ceres Solver from source.
RUN git clone https://github.com/ceres-solver/ceres-solver.git && \
    cd ceres-solver && \
    git checkout ${CERES_VERSION} && \
    mkdir build && \
    cd build && \
    cmake .. \
        -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_TESTING=OFF \
        -DBUILD_EXAMPLES=OFF \
        -DBUILD_BENCHMARKS=OFF \
        -DUSE_CUDA=ON \
        -DCUDSS=ON \
        -DBLA_VENDOR=Intel10_64lp \
        -DCMAKE_INSTALL_PREFIX=/usr/local && \
    ninja install

# Build and install COLMAP.
RUN git clone https://github.com/colmap/colmap.git
RUN cd colmap && \
    git fetch https://github.com/colmap/colmap.git ${COLMAP_GIT_COMMIT} && \
    git checkout FETCH_HEAD && \
    mkdir build && \
    cd build && \
    cmake .. \
        -GNinja \
        -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES} \
        -DCMAKE_INSTALL_PREFIX=/colmap-install \
        -DBLA_VENDOR=Intel10_64lp && \
    ninja install


RUN cd ../ && \
    git clone https://github.com/colmap/glomap.git && \
    cd glomap/ && \
    mkdir build && \
    cd build && \
    cmake .. \
          -GNinja \
          -DCMAKE_INSTALL_PREFIX=/glomap-install && \
    ninja && ninja install


# Build GDAL + PDAL from source into an isolated /deps-install prefix.  PDAL is NOT
# packaged for Ubuntu 24.04 (noble) — it never migrated into the release — so the apt
# route used elsewhere is unavailable; PDAL also requires GDAL, so both are built here
# (mirroring services/orthomosaic_generation/Dockerfile).  The SFM service uses the
# `pdal` CLI to reproject the dense cloud ECEF -> UTM and write fused_utm.ply.
RUN apt-get update && apt-get install -y --no-install-recommends \
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
        libexpat1-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/src
# Build GDAL minimal (no optional drivers, no curl): the SFM service only needs PROJ/SRS
# for PDAL's ECEF->UTM reprojection, and a minimal build keeps the runtime shared-library
# closure deterministic — exactly the core libs installed in the runtime stage (apt pulls
# their transitive deps such as libwebp/liblzma/libdeflate via libtiff6).
#
# Install with prefix=/usr/local but stage into /deps-install via DESTDIR, so the
# compiled-in data path (<prefix>/share/gdal) and RPATH stay correct after the runtime
# stage copies /deps-install/usr/local -> /usr/local.
RUN git clone --depth 1 --branch v3.12.2 https://github.com/OSGeo/gdal.git gdal && \
    cmake -S gdal -B gdal/build -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_SHARED_LIBS=ON \
        -DGDAL_BUILD_OPTIONAL_DRIVERS=OFF \
        -DOGR_BUILD_OPTIONAL_DRIVERS=OFF \
        -DGDAL_USE_CURL=OFF && \
    DESTDIR=/deps-install ninja -C gdal/build install && \
    cp -a /deps-install/usr/local/. /usr/local/ && \
    ldconfig && \
    rm -rf gdal

RUN git clone --depth 1 --branch 2.9.2 https://github.com/PDAL/PDAL.git pdal && \
    cmake -S pdal -B pdal/build -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DCMAKE_PREFIX_PATH=/usr/local && \
    DESTDIR=/deps-install ninja -C pdal/build install && \
    rm -rf pdal


#
# Docker runtime stage.
#
FROM nvidia/cuda:${NVIDIA_CUDA_VERSION}-runtime-ubuntu${UBUNTU_VERSION} AS runtime

# Minimal dependencies to run COLMAP binary compiled in the builder stage.
# Removed libceres4t64.
# Added libgflags2.2 and SuiteSparse runtime libs (libamd3, libcholmod5, etc.) for Ubuntu 24.04.
RUN apt-get update && \
    apt-get install -y --no-install-recommends --no-install-suggests \
        libboost-program-options1.83.0 \
        libc6 \
        libomp5 \
        libopengl0 \
        libmetis5 \
        libgflags2.2 \
        libamd3 \
        libbtf2 \
        libcamd3 \
        libccolamd3 \
        libcholmod5 \
        libcolamd3 \
        libcxsparse4 \
        libklu2 \
        libldl3 \
        librbio4 \
        libsuitesparseconfig7 \
        libsuitesparse-dev \
        libumfpack6 \
        libfreeimage3 \
        libgcc-s1 \
        libgl1 \
        libglew2.2 \
        libgoogle-glog0v6t64 \
        libqt6core6 \
        libqt6gui6 \
        libqt6widgets6 \
        libqt6openglwidgets6 \
        libcurl4 \
        libssl3t64 \
        libmkl-locale \
        libmkl-intel-lp64 \
        libmkl-intel-thread \
        libmkl-core \
        libproj25 \
        proj-data \
        libgeotiff5 \
        liblaszip8 \
        libtiff6 \
        libjpeg-turbo8 \
        libpng16-16t64 \
        libexpat1 \
        libsqlite3-0 \
        libxml2 \
        libzstd1 \
        python3 \
        python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy compiled Ceres Solver from builder to runtime.
COPY --from=builder /usr/local/include/ceres /usr/local/include/ceres
COPY --from=builder /usr/local/lib/libceres.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/cmake/Ceres /usr/local/lib/cmake/Ceres

# Copy all files from /colmap-install/ in the builder stage to /usr/local/
COPY --from=builder /colmap-install/ /usr/local/
COPY --from=builder /glomap-install /usr/local/

# Copy the from-source GDAL + PDAL (binaries, libs, includes, and the GDAL data dir).
# Staged under /deps-install/usr/local via DESTDIR in the builder.
COPY --from=builder /deps-install/usr/local/ /usr/local/
RUN ldconfig

# Download vocabulary tree once at build time so COLMAP never fetches it at runtime.
# 256K-word FAISS tree is a good balance: fast retrieval, compact size (~200 MB).
RUN apt-get update && apt-get install -y --no-install-recommends wget && \
    mkdir -p /usr/local/share/colmap && \
    wget -q -O /usr/local/share/colmap/vocab_tree_flickr100K_words256K.bin \
        https://github.com/colmap/colmap/releases/download/3.11.1/vocab_tree_faiss_flickr100K_words256K.bin && \
    apt-get remove -y wget && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/sfm/requirements.txt .

RUN pip install --break-system-packages -r requirements.txt

COPY infrastructure/ ./infrastructure/
COPY shared/ ./shared/
COPY services/sfm/ ./services/sfm/

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"SFM_SERVICE_PORT\",8002)}/health/')"
