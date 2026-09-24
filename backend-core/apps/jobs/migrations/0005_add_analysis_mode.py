"""Add analysis_mode field to ProcessingJob."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0004_alter_processingjob_last_successful_stage_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="processingjob",
            name="analysis_mode",
            field=models.CharField(
                choices=[("fast", "Fast (RGB only)"), ("full", "Full (Multispectral + Indices)")],
                default="fast",
                help_text="Analysis mode: fast (RGB only) or full (multispectral + indices)",
                max_length=10,
            ),
        ),
    ]
