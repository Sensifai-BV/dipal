import pytest
from core.organizations.domain.models import Organization

@pytest.mark.django_db
def test_admin_can_create_org(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    payload = {'name': 'TestOrg'}
    response = api_client.post('/v1/organizations/', payload)
    assert response.status_code == 201
    assert Organization.objects.filter(name='TestOrg').exists()
