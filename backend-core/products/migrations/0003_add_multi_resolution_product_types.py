from django.db import migrations, models


class Migration(migrations.Migration):
    """Add multi-resolution orthomosaic product types: orthomosaic_2x, orthomosaic_4x, orthomosaic_8x."""

    dependencies = [
        ("products", "0002_rename_products_pr_dataset_idx_products_pr_dataset_2192a8_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="type",
            field=models.CharField(
                choices=[
                    ("orthomosaic", "2D Orthomosaic"),
                    ("dsm", "Digital Surface Model (DSM)"),
                    ("dem", "Digital Elevation Model (DEM)"),
                    ("hillshade", "Hillshade/Terrain Visualization"),
                    ("pointcloud", "3D Point Cloud"),
                    ("mesh", "3D Mesh Model"),
                    ("sparse_reconstruction", "Sparse Reconstruction"),
                    ("dense_reconstruction", "Dense Reconstruction"),
                    ("ndvi", "NDVI Map"),
                    ("ndre", "NDRE Map"),
                    ("gndvi", "GNDVI Map"),
                    ("calibrated_reflectance", "Calibrated Reflectance"),
                    ("band_manifest", "Band Classification Manifest"),
                    ("orthomosaic_2x", "Orthomosaic 2\u00d7 Downsample"),
                    ("orthomosaic_4x", "Orthomosaic 4\u00d7 Downsample"),
                    ("orthomosaic_8x", "Orthomosaic 8\u00d7 Downsample"),
                    ("preview", "Preview/Thumbnail"),
                    ("statistics", "Statistics/Metadata"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
