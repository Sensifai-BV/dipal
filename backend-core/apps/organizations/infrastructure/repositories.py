from django.shortcuts import get_object_or_404
from accounts.models.organization import Organization


class OrganizationRepository:


    def get_all(self):
        return Organization.objects.all()

    def get_by_id(self, org_id):
        return get_object_or_404(Organization, pk=org_id)

    def create(self, data: dict) -> Organization:
        return Organization.objects.create(**data)

    def update(self, org: Organization, data: dict) -> Organization:
        for key, value in data.items():
            setattr(org, key, value)
        org.save()
        return org

    def delete(self, org: Organization):
        org.delete()
