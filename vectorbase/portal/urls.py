from django.urls import path

from portal import views

urlpatterns = [
    path("", views.search, name="search"),
]
