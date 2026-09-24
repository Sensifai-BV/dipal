from django.db import migrations


def add_downloading_status(apps, schema_editor):
    UploadStatus = apps.get_model('uploads', 'UploadStatus')
    UploadStatus.objects.get_or_create(
        name='DOWNLOADING',
        defaults={'label': 'Downloading'}
    )


class Migration(migrations.Migration):
    dependencies = [
        ('uploads', '0007_aiprocessingjob_type_alter_aiprocessingjob_dataset'),
    ]

    operations = [
        migrations.RunPython(add_downloading_status, reverse_code=migrations.RunPython.noop),
    ]
