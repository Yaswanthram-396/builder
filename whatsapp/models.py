from django.db import models

class Lead(models.Model):
    LEAD_TYPES = (
        ("BUYER", "Buyer"),
        ("SELLER", "Seller"),
        ("UNKNOWN", "Unknown"),
    )

    STATUS_CHOICES = (
        ("NEW", "New"),
        ("QUALIFIED", "Qualified"),
        ("UNQUALIFIED", "Unqualified"),
    )

    SEGMENT_CHOICES = (
        ("PREMIUM", "Premium"),
        ("ACTIVE", "Active"),
        ("PROSPECT", "Prospect"),
        ("INACTIVE", "Inactive"),
    )

    phone = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    lead_type = models.CharField(max_length=10, choices=LEAD_TYPES, default="UNKNOWN")

    data = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NEW")
    score = models.IntegerField(null=True, blank=True)
    segment = models.CharField(max_length=10, choices=SEGMENT_CHOICES, default="INACTIVE")
    rejection_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone} ({self.lead_type})"


class ConversationState(models.Model):
    phone = models.CharField(max_length=20, unique=True)
    current_step = models.CharField(max_length=50, default="INIT")  # init / BUY_Q1 / SELL_Q3 etc
    last_message = models.TextField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone} -> {self.current_step}"

class Property(models.Model):
    SELLER = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="properties")

    property_type = models.CharField(max_length=50, null=True, blank=True)
    area_sqft = models.CharField(max_length=50, null=True, blank=True)
    bhk = models.CharField(max_length=50, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    price_range = models.CharField(max_length=100, null=True, blank=True)
    amenities = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.property_type} - {self.bhk} - {self.location}"
