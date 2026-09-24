"""Product model for storing processing outputs"""
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
import uuid


class Product(models.Model):
    """
    Processing outputs from jobs (orthomosaic, DEM, DSM, pointcloud, mesh, etc.)
    Based on ERD specification
    """
    
    # Product type categories with user-friendly display names
    PRODUCT_TYPE_CHOICES = [
        # 2D Outputs (Raster/Images)
        ('orthomosaic', '2D Orthomosaic'),
        ('dsm', 'Digital Surface Model (DSM)'),
        ('dem', 'Digital Elevation Model (DEM)'),
        ('hillshade', 'Hillshade/Terrain Visualization'),
        
        # 3D Outputs (Point Clouds & Meshes)
        ('pointcloud', '3D Point Cloud'),
        ('pointcloud_utm', '3D Point Cloud (UTM)'),
        ('mesh', '3D Mesh Model'),
        
        # Reconstruction Outputs
        ('sparse_reconstruction', 'Sparse Reconstruction'),
        ('dense_reconstruction', 'Dense Reconstruction'),
        
        # Vegetation Indices (Radiometric Calibration)
        ('ndvi', 'NDVI Map'),
        ('ndre', 'NDRE Map'),
        ('gndvi', 'GNDVI Map'),
        ('calibrated_reflectance', 'Calibrated Reflectance'),
        ('band_manifest', 'Band Classification Manifest'),
        
        # Multi-Resolution Outputs
        ('orthomosaic_2x', 'Orthomosaic 2× Downsample'),
        ('orthomosaic_4x', 'Orthomosaic 4× Downsample'),
        ('orthomosaic_8x', 'Orthomosaic 8× Downsample'),

        # Raw Band Orthos (GeoTIFF)
        ('band_green', 'Green Band Orthomosaic'),
        ('band_red', 'Red Band Orthomosaic'),
        ('band_red_edge', 'Red Edge Band Orthomosaic'),
        ('band_nir', 'NIR Band Orthomosaic'),
        ('band_blue', 'Blue Band Orthomosaic'),

        # Other
        ('preview', 'Preview/Thumbnail'),
        ('statistics', 'Statistics/Metadata'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Foreign Keys
    dataset = models.ForeignKey(
        'uploads.Dataset',
        on_delete=models.CASCADE,
        related_name='products',
        db_column='dataset_id'
    )
    
    job = models.ForeignKey(
        'jobs.ProcessingJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        db_column='job_id'
    )
    
    # Product details
    type = models.CharField(max_length=50, choices=PRODUCT_TYPE_CHOICES)
    uri = models.CharField(max_length=512, help_text="S3 key or file path")
    
    # Spatial information (PostGIS geometry)
    footprint = models.PolygonField(
        srid=4326,
        null=True,
        blank=True,
        help_text="Product footprint in EPSG:4326"
    )
    
    # Product metadata
    resolution_cm = models.FloatField(
        null=True,
        blank=True,
        help_text="Resolution in cm/pixel"
    )
    
    bands = ArrayField(
        models.CharField(max_length=50),
        null=True,
        blank=True,
        help_text="List of spectral bands"
    )
    
    stats = models.JSONField(
        null=True,
        blank=True,
        help_text="Product statistics and metadata"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'products'
        db_table = 'products_product'
        indexes = [
            models.Index(fields=['dataset', 'type']),
            models.Index(fields=['job']),
            models.Index(fields=['created_at']),
        ]
        # Add spatial index on footprint (done automatically by PostGIS)
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.dataset.name if self.dataset else 'Unknown'} ({self.id})"
    
    def get_category(self):
        """Return the category of this product (2D, 3D, Calibration, or Other)."""
        if self.type in ['orthomosaic', 'dsm', 'dem', 'hillshade', 'orthomosaic_2x', 'orthomosaic_4x', 'orthomosaic_8x']:
            return '2D Raster'
        elif self.type in ['pointcloud', 'pointcloud_utm', 'mesh']:
            return '3D Model'
        elif self.type in ['sparse_reconstruction', 'dense_reconstruction']:
            return 'Reconstruction'
        elif self.type in ['ndvi', 'ndre', 'gndvi', 'calibrated_reflectance', 'band_manifest',
                           'band_green', 'band_red', 'band_red_edge', 'band_nir', 'band_blue']:
            return 'Calibration'
        else:
            return 'Other'
