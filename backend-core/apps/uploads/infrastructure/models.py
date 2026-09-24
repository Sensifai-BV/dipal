import uuid
from django.db import models
from django.contrib.gis.db import models as gis_models
from accounts.models import Organization


class UploadStatus(models.Model):
    """
    Model to store different upload statuses dynamically from the DB.
    """
    # We use a CharField for the name as a "code" and an Integer ID for relations.
    # e.g., name='PENDING', label='Pending'
    name = models.CharField(max_length=50, unique=True, help_text="The status code, e.g., 'PENDING'")
    label = models.CharField(max_length=100, help_text="A human-readable label, e.g., 'Pending'")

    class Meta:
        db_table = 'uploads_statuses'
        verbose_name_plural = "Upload Statuses"

    def __str__(self):
        return self.label


# --------------------------------------------------------
# ------------ AI Jobs Uploads Models --------------------
# --------------------------------------------------------

class AIProcessingJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    dataset = models.ForeignKey(
        'Dataset',
        on_delete=models.CASCADE,
        related_name='ai_jobs',
        null=True,
        blank=True
    )

    type = models.CharField(max_length=50, help_text="e.g. DETECTION, SEGMENTATION")

    batch_id = models.UUIDField(null=True, blank=True, help_text="Batch ID provided by frontend")

    status = models.ForeignKey(
        UploadStatus,
        on_delete=models.PROTECT,
        related_name='ai_jobs'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job {self.id} - {self.status.name}"


class AIResultFile(models.Model):
    job = models.ForeignKey(AIProcessingJob, on_delete=models.CASCADE, related_name='files')
    file_name = models.CharField(max_length=255)
    s3_key = models.CharField(max_length=1000)
    file_type = models.CharField(max_length=50)

    def __str__(self):
        return self.file_name

#--------------------------------------------------------
# Helper function to get the default status ID
# This prevents errors during migration if the object doesn't exist yet.
def get_default_status():
    # We will ensure 'PENDING' status is created in a data migration.
    # We use .first() to avoid errors if get() fails during initial migrations.
    status = UploadStatus.objects.filter(name='PENDING').first()
    if status:
        return status.pk
    return None

class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='datasets')

    name = models.CharField(max_length=255)
    platform = models.CharField(max_length=100, blank=True, null=True)

    capture_start = models.DateTimeField(null=True, blank=True)
    capture_end = models.DateTimeField(null=True, blank=True)

    crs = models.CharField(max_length=100, blank=True, null=True, default="EPSG:4326")

    # Bounding Box (PostGIS)
    bbox = gis_models.PolygonField(null=True, blank=True)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'uploads_datasets'


class Image(models.Model):

    class FileType(models.TextChoices):
        IMAGE = 'IMAGE', 'Image'
        ARCHIVE = 'ARCHIVE', 'Archive'
        METADATA = 'METADATA', 'Metadata'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='images')

    status = models.ForeignKey(
        UploadStatus,
        on_delete=models.PROTECT,
        related_name='images',
        default=get_default_status,  # Set default to 'PENDING'
        null= True , # Temporarily allow null for migration purposes
        blank = True
    )
    # status = models.CharField(max_length=50, null=True, blank=True)

    user_id = models.UUIDField(help_text="ID of the user who uploaded")
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, default='application/octet-stream')
    s3_key = models.CharField(max_length=1024)
    s3_upload_id = models.CharField(max_length=255, blank=True, null=True)

    file_size = models.BigIntegerField(null=True, blank=True, help_text="Size of the file in bytes")
    batch_id = models.UUIDField(null=True, blank=True, help_text="Unique ID for the upload session/batch")
    parent_image = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')

    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.IMAGE,
        help_text="Distinguishes between single images and archives (zip)"
    )

    checksum = models.CharField(max_length=255, blank=True, null=True)

    # Metadata extracted from image
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)

    # JSON Fields for detailed meta
    exif = models.JSONField(default=dict, blank=True)
    imu = models.JSONField(default=dict, blank=True)

    error_message = models.TextField(blank=True, null=True, help_text="Error message if upload/processing failed")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'uploads_images'