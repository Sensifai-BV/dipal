# PhotoGear Image Analysis Core - Documentation

Comprehensive documentation for the PhotoGear photogrammetry processing pipeline.

## 📁 Documentation Structure

### 🏗️ [Architecture](architecture/)
System design and architecture documentation
- [ARCHITECTURE.md](architecture/ARCHITECTURE.md) - Complete system architecture, data flow, and processing pipeline

### 🚀 [Deployment](deployment/)
Service deployment and operations
- [RUNNING_SERVICES.md](deployment/RUNNING_SERVICES.md) - How to run services individually or together, configuration options

### 📘 [Guides](guides/)
User guides and tutorials
- [QUICK_START.md](guides/QUICK_START.md) - Get started quickly with the system
- [visualization.md](guides/visualization.md) - Visualization tools and methods

### 🔧 [Services](services/)
Individual service documentation
- [API_GATEWAY.md](services/API_GATEWAY.md) - API Gateway endpoints and orchestration
- [orthomosaic_generation.md](services/orthomosaic_generation.md) - Orthomosaic generation service
- [MULTISPECTRAL_ANALYSIS.md](services/MULTISPECTRAL_ANALYSIS.md) - Multispectral pipeline: reflectance, band orthorectification, vegetation indices

### 💾 [Storage](storage/)
Storage system documentation
- [storage_system.md](storage/storage_system.md) - Storage architecture and implementation
- [presigned_url_driver.md](storage/presigned_url_driver.md) - Presigned URL driver documentation

---

## 📚 Quick Navigation

### Getting Started
1. **First Time Setup**: Start with [QUICK_START.md](guides/QUICK_START.md)
2. **Running Services**: See [RUNNING_SERVICES.md](deployment/RUNNING_SERVICES.md)
3. **Understanding the System**: Read [ARCHITECTURE.md](architecture/ARCHITECTURE.md)

### Common Tasks
- **Submit a Processing Job**: [API_GATEWAY.md](services/API_GATEWAY.md#1-run-job)
- **Configure Services**: [RUNNING_SERVICES.md](deployment/RUNNING_SERVICES.md#configuration)
- **Visualize Results**: [visualization.md](guides/visualization.md)

### For Developers
- **System Architecture**: [ARCHITECTURE.md](architecture/ARCHITECTURE.md)
- **Implementation Summary**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Storage System**: [storage_system.md](storage/storage_system.md)

---

## 🚀 Features

- **Microservices Architecture**: Modular, scalable processing pipeline
- **Feature Extraction**: SIFT feature detection with GPU acceleration
- **Feature Matching**: Exhaustive matching with cross-checking
- **Sparse Reconstruction**: Bundle adjustment and triangulation
- **Dense Reconstruction**: Dense point cloud generation
- **Orthomosaic Generation**: High-resolution orthomosaic and DSM creation
- **Radiometric Calibration**: DN-to-reflectance conversion for spectral bands
- **Multispectral Analysis**: Band orthorectification + NDVI/NDRE/GNDVI (v0.6.0)
- **Smart Database Management**: Reuses existing features when available
- **Configurable Services**: Run all together or distributed across machines
- **Analysis Modes**: Fast (RGB-only, GSD×2) and Full (RGB + multispectral)

## 🛠️ System Components

```
┌──────────────────────────────────────────┐
│         Backend (Django)                 │
│         http://backend:8000              │
└────────────────┬─────────────────────────┘
                 │
                 │ HTTP Request
                 ▼
┌──────────────────────────────────────────┐
│      API Gateway (Port 8080)             │
│  - Orchestrates pipeline                 │
│  - Downloads dataset                     │
│  - Tracks progress                       │
└────┬──────────┬──────────┬───────────────┘
     │          │          │
     ▼          ▼          ▼
┌─────────┐ ┌───────┐ ┌──────────────┐
│Calib    │ │  SFM  │ │ Orthomosaic  │
│:8001    │ │ :8002 │ │    :8003     │
└─────────┘ └───────┘ └──────────────┘
```

## ⚡ Quick Install

```bash
# Copy environment configuration
cp .env.example .env

# Create Docker network
docker network create image_processing_network

# Run all services
docker-compose up --build
```

For more detailed setup instructions, see [RUNNING_SERVICES.md](deployment/RUNNING_SERVICES.md).

## 📖 Additional Resources

- **Main README**: [../README.md](../README.md) - Project overview
- **COLMAP Documentation**: External COLMAP configuration details
- **API Documentation**: Interactive API docs at `http://localhost:8080/docs`

---

## 🤝 Contributing

When adding new documentation:
1. Place files in the appropriate category folder
2. Update this README with links
3. Follow the existing naming conventions
4. Include code examples where relevant

## 📝 Legacy Documentation

The following documentation is retained for reference:
- [README_LEGACY.md](README_LEGACY.md) - Original SfM pipeline documentation (preserved from original README.md)
