# Generated 2026-04-28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_alter_product_type'),
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
                    ('band_green', 'Green Band Orthomosaic (ZIP)'),
                    ('band_red', 'Red Band Orthomosaic (ZIP)'),
                    ('band_red_edge', 'Red Edge Band Orthomosaic (ZIP)'),
                    ('band_nir', 'NIR Band Orthomosaic (ZIP)'),
                    ('band_blue', 'Blue Band Orthomosaic (ZIP)'),
                    ('preview', 'Preview/Thumbnail'),
                    ('statistics', 'Statistics/Metadata'),
                ],
                max_length=50,
            ),
        ),
    ]
