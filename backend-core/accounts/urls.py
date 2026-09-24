from django.urls import path

from accounts.views.login import AccountLoginUserAPIView
from accounts.views.organization_create import OrganizationCreateAPIView
from accounts.views.organization_detail import OrganizationDetailAPIView
from accounts.views.organization_list import OrganizationListAPIView
from accounts.views.profile import AccountProfileAPIView
from accounts.views.register import AccountRegisterAPIView

urlpatterns = [
    path("login/", AccountLoginUserAPIView.as_view(), name="account-login"),
    path("register/", AccountRegisterAPIView.as_view(), name="account-register"),
    path("profile/", AccountProfileAPIView.as_view(), name="account-profile"),
    path("organizations/create/", OrganizationCreateAPIView.as_view(), name="organizations-create"),
    path("organizations/list/", OrganizationListAPIView.as_view(), name="organizations-list"),
    path("organizations/detail/<int:object_id>/", OrganizationDetailAPIView.as_view(), name="organizations-detail"),
]
