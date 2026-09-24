# Generated 2026-06-15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_add_raw_band_product_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='type',
            field=models.CharField(
                choices=[
                    ('orthomosaic', '2D Orthomosaic'),
                    ('dsm', 'Digital Surface Model (DSM)'),
                    ('dem', 'Digital Elevation Model (DEM)'),
                    ('hillshade', 'Hillshade/Terrain Visualization'),
                    ('pointcloud', '3D Point Cloud'),
                    ('pointcloud_utm', '3D Point Cloud (UTM)'),
                    ('mesh', '3D Mesh Model'),
                    ('sparse_reconstruction', 'Sparse Reconstruction'),
                    ('dense_reconstruction', 'Dense Reconstruction'),
                    ('ndvi', 'NDVI Map'),
                    ('ndre', 'NDRE Map'),
                    ('gndvi', 'GNDVI Map'),
                    ('calibrated_reflectance', 'Calibrated Reflectance'),
                    ('band_manifest', 'Band Classification Manifest'),
                    ('orthomosaic_2x', 'Orthomosaic 2× Downsample'),
                    ('orthomosaic_4x', 'Orthomosaic 4× Downsample'),
                    ('orthomosaic_8x', 'Orthomosaic 8× Downsample'),
                    ('band_green', 'Green Band Orthomosaic'),
                    ('band_red', 'Red Band Orthomosaic'),
                    ('band_red_edge', 'Red Edge Band Orthomosaic'),
                    ('band_nir', 'NIR Band Orthomosaic'),
                    ('band_blue', 'Blue Band Orthomosaic'),
                    ('preview', 'Preview/Thumbnail'),
                    ('statistics', 'Statistics/Metadata'),
                ],
                max_length=50,
            ),
        ),
    ]
