from django.db.models import QuerySet
from django.http import QueryDict

from accounts.filters.organization import OrganizationModelFilters
from accounts.models.organization import Organization
from accounts.models.user import UserModel
from config.logging_config import LoggingConfig, container


class OrganizationQueryService:
    def __init__(self, logging_config: LoggingConfig = None):
        """Initialize service with logging configuration."""
        if logging_config is None:
            logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    def get_filtered_queryset(self, *, user: UserModel, object_id: int, query_params: QueryDict):
        """Get a single filtered organizations by ID."""
        self.logger.debug(f"Fetching organizations with ID: {object_id} for user: {user.email}")
        
        queryset = Organization.objects.filter(pk=object_id, user=user)


        if query_params:
            filterset = OrganizationModelFilters(query_params, queryset=queryset)
            if filterset.is_valid():
                queryset = filterset.qs
            else:
                self.logger.warning(f"Invalid filter parameters: {filterset.errors}")

        queryset = queryset.first()

        if queryset:
            self.logger.info(f"Organization {object_id} found for user {user.email}")
        else:
            self.logger.warning(f"Organization {object_id} not found for user {user.email}")
            
        return queryset

    def all_filtered_queryset(self, *, user: UserModel, query_params: QueryDict):
        """Get all filtered organizations for a user."""
        self.logger.debug(f"Fetching all organizations for user: {user.email}")
        
        queryset = Organization.objects.filter(user=user)
        count = queryset.count()
        
        self.logger.info(f"Found {count} organizations for user {user.email}")

        if queryset:
            filterset = OrganizationModelFilters(query_params, queryset=queryset)
            if filterset.is_valid():
                queryset = filterset.qs
                filtered_count = queryset.count()
                if filtered_count != count:
                    self.logger.debug(f"Filtered down to {filtered_count} organizations")
            else:
                self.logger.warning(f"Invalid filter parameters: {filterset.errors}")

        return queryset

    def apply_ordering(self, *, queryset: QuerySet[Organization], ordering_param: str):
        """Apply ordering to queryset."""
        if ordering_param:
            self.logger.debug(f"Applying ordering: {ordering_param}")
            return queryset.order_by(ordering_param)

        return queryset
