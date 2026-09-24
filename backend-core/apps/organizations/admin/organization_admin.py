from django.contrib import admin
from accounts.models.organization import Organization
from accounts.models.user import UserModel


class UserInline(admin.TabularInline):
    model = UserModel
    fields = ('email', 'role', 'first_name', 'last_name')
    readonly_fields = ('email', 'first_name', 'last_name')
    extra = 0
    can_delete = False


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):

    list_display = ('id', 'name', 'created_at', 'updated_at')

    search_fields = ('name', 'description')

    list_filter = ('created_at',)


    inlines = [UserInline]
