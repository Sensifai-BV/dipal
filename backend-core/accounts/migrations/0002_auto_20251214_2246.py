from django.db import migrations

ROLES = [
    {'id': 1, 'name': 'admin', 'label': 'Admin'},  # RoleName.ADMIN
    {'id': 2, 'name': 'user', 'label': 'Owner'},    # RoleName.USER
]

def populate_roles(apps, schema_editor):
    """
    Creates the initial set of roles in the database.
    """

    Role = apps.get_model('accounts', 'Role')

    for role_data in ROLES:

        Role.objects.get_or_create(
            id=role_data['id'],
            defaults={
                'name': role_data['name'],
            }
        )

def reverse_func(apps, schema_editor):
    """
    Deletes the roles if migration is rolled back.
    """
    Role = apps.get_model('accounts', 'Role')
    role_ids = [role['id'] for role in ROLES]
    Role.objects.filter(id__in=role_ids).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_roles, reverse_func)
    ]



