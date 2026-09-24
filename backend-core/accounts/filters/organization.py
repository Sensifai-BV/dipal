import django_filters

from accounts.models.organization import Organization


class OrganizationModelFilters(django_filters.FilterSet):
    class Meta:
        model = Organization
        fields = '__all__'
