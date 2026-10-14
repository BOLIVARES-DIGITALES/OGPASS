from django.urls import path
from . import views

urlpatterns = [
    path('w/<slug:code>/', views.landing, name='tag-portal'),
    path('w/<slug:code>/activate/', views.activate, name='activate-tag-portal'),
    path('w/<slug:code>/block/', views.block, name='block-tag-portal'),
    path('api/v1/tags/<slug:code>/', views.public_state, name='tag-portal-state'),
    path('my/tags/', views.my_tags, name='my-tag-portals'),
    path('my/tags/<int:tag_id>/portal/', views.provision, name='provision-tag-portal'),
]
