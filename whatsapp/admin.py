from django.contrib import admin
from .models import Lead, ConversationState
# Register your models here.
admin.site.register(Lead)
admin.site.register(ConversationState)