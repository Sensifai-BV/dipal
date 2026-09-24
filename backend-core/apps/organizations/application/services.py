from apps.organizations.infrastructure.repositories import OrganizationRepository
from accounts.models.user import UserModel

class OrganizationService:

    def __init__(self):
        self.repo = OrganizationRepository()

    def list_organizations(self, user):

        if user.is_staff or user.is_superuser:
            return self.repo.get_all()

        if user.organization:
            return [user.organization]

        return []

    def get(self, pk):
        return self.repo.get_by_id(pk)

    def create_organization(self, user, data):
        org = self.repo.create(data)


        user.organization = org

        if hasattr(UserModel.Role, 'OWNER'):
            user.role = UserModel.Role.OWNER

        user.save()

        return org

    def update(self, pk, data):
        org = self.repo.get_by_id(pk)
        return self.repo.update(org, data)

    def delete(self, pk):
        org = self.repo.get_by_id(pk)
        self.repo.delete(org)
