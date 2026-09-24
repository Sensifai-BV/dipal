# Generated migration for retry functionality

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_add_s3_urls_and_error_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='processingjob',
            name='retry_count',
            field=models.PositiveIntegerField(default=0, help_text='Number of times this job has been retried'),
        ),
        migrations.AddField(
            model_name='processingjob',
            name='last_successful_stage',
            field=models.CharField(
                blank=True,
                choices=[
                    ('queued', 'Queued'),
                    ('sfm', 'Structure from Motion'),
                    ('mvs', 'Multi View Stereo'),
                    ('publishing', 'Publishing')
                ],
                help_text='Last stage completed successfully (for resume on retry)',
                max_length=20,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='processingjob',
            name='original_job_id',
            field=models.UUIDField(blank=True, help_text='Original job ID if this is a retry', null=True),
        ),
        migrations.AddField(
            model_name='processingjob',
            name='can_retry',
            field=models.BooleanField(default=True, help_text='Whether this job can be retried if it fails'),
        ),
    ]
