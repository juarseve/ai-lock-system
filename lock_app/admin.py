from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'secret_phrase', 'is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'secret_phrase')
    list_filter = ('is_active',)
