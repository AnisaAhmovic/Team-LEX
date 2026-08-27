from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health_check, name="health-check"),
    path("retrieve/", views.policy_evidence, name="policy-evidence"),
    # Keep the original proof-of-concept URL working for existing team setups.
    path("test/", views.health_check, name="test-endpoint"),
]
