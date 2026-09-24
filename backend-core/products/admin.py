from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Product


@admin.register(Product)
class ProductAdmin(GISModelAdmin):
    list_display = ('id', 'type', 'dataset', 'job', 'resolution_cm', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('id', 'dataset__id', 'job__id', 'uri')
    readonly_fields = ('id', 'created_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

