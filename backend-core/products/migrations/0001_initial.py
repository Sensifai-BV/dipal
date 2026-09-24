# Generated manually for Product model

from django.db import migrations, models
import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('uploads', '0001_initial'),  # Assuming uploads has initial migration
        ('jobs', '0001_initial'),  # Assuming jobs has initial migration
    ]

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type', models.CharField(choices=[('orthomosaic', 'Orthomosaic'), ('dem', 'Digital Elevation Model'), ('dsm', 'Digital Surface Model'), ('pointcloud', 'Point Cloud'), ('mesh', '3D Mesh'), ('preview', 'Preview/Thumbnail'), ('sparse_model', 'Sparse Reconstruction'), ('dense_model', 'Dense Reconstruction')], max_length=50)),
                ('uri', models.CharField(help_text='S3 key or file path', max_length=512)),
                ('footprint', django.contrib.gis.db.models.fields.PolygonField(blank=True, help_text='Product footprint in EPSG:4326', null=True, srid=4326)),
                ('resolution_cm', models.FloatField(blank=True, help_text='Resolution in cm/pixel', null=True)),
                ('bands', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), blank=True, help_text='List of spectral bands', null=True, size=None)),
                ('stats', models.JSONField(blank=True, help_text='Product statistics and metadata', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dataset', models.ForeignKey(db_column='dataset_id', on_delete=django.db.models.deletion.CASCADE, related_name='products', to='uploads.dataset')),
                ('job', models.ForeignKey(blank=True, db_column='job_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='jobs.processingjob')),
            ],
            options={
                'db_table': 'products_product',
                'indexes': [
                    models.Index(fields=['dataset', 'type'], name='products_pr_dataset_idx'),
                    models.Index(fields=['job'], name='products_pr_job_idx'),
                    models.Index(fields=['created_at'], name='products_pr_created_idx'),
                ],
            },
        ),
    ]
