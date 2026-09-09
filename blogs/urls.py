# blogs/urls.py
from django.urls import path
from blogs.views import (
    BlogsListView,
    BlogPostDetailView,
    BlogPostCreateView,
    BlogPostEditView,
    BlogPostDeleteView,
)

app_name = 'blogs'

urlpatterns = [
    path('', BlogsListView.as_view(), name='blogs'),
    path('create/', BlogPostCreateView.as_view(), name='create_blog_post'),
    path('<uuid:pk>/', BlogPostDetailView.as_view(), name='blog_post'),
    path('<uuid:pk>/edit/', BlogPostEditView.as_view(), name='edit_blog_post'),
    path('<uuid:pk>/delete/', BlogPostDeleteView.as_view(), name='delete_blog_post'),
]
