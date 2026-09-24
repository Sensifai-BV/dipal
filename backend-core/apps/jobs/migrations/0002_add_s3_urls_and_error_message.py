# Generated manually for adding error message field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='processingjob',
            name='error_message',
            field=models.TextField(blank=True, help_text='Error details if job failed', null=True),
        ),
    ]
