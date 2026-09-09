# main/urls.py
from django.contrib import admin
from django.urls import path, re_path
from django.contrib.sitemaps.views import sitemap
from main.views import (
    LoginView, SignupView, LogoutView,
    PasswordResetRequestView, PasswordResetView,
    SlugCreateView, SlugEditView, SlugDeleteView, SlugView,
    SlugDynamicCreateView, SlugDynamicEditView,
    ProfileView, SendEmailView, ValidateView, EditPasswordView,
    robots_txt
)
from main.sitemaps import StaticAppSitemap, SlugDatabaseSitemap, DynamicAppSitemap
from django.conf import settings
from django.conf.urls.static import static


sitemaps = {
    'static': StaticAppSitemap,
    'slugs': SlugDatabaseSitemap,
    'dynamic': DynamicAppSitemap,
}


urlpatterns = [
    path('admin/', admin.site.urls),

    # Dynamic SEO endpoints (Handles requests with or without trailing slashes)
    re_path(r'^robots\.txt/?$', robots_txt, name='robots_txt'),
    re_path(r'^sitemap\.xml/?$', sitemap, {'sitemaps': sitemaps}, name='sitemap'),

    # Auth & Profile routes
    path('login/', LoginView.as_view(), name='login'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit_password/', EditPasswordView.as_view(), name='edit_password'),

    # Validation routes
    path('profile/send_email/', SendEmailView.as_view(), name='send_validation_email'),
    path('profile/validate/<uuid:token>/', ValidateView.as_view(), name='validate_account'),

    # Password Reset routes
    path('generate-prt/', PasswordResetRequestView.as_view(), name='generate_prt'),
    path('reset-password/<uuid:token>/', PasswordResetView.as_view(), name='reset_password'),

    # Static slug management routes
    path('slug/create/', SlugCreateView.as_view(), name='slug'),
    path('slug/edit/<uuid:slug_id>/', SlugEditView.as_view(), name='slug_edit'),
    path('slug/delete/', SlugDeleteView.as_view(), name='slug_delete'),

    # Dynamic slug instance routes: pk in slug_parent/<uuid:parent_id>/...
    # is the is_dynamic=True Slug whose json schema drives the form.
    path('slug_parent/<uuid:parent_id>/create/',
         SlugDynamicCreateView.as_view(), name='slug_dynamic_create'),
    path('slug_parent/<uuid:parent_id>/<uuid:slug_id>/edit/',
         SlugDynamicEditView.as_view(), name='slug_dynamic_edit'),

    # Catch-all slug routes MUST stay at the very bottom
    path('<path:slug_path>/', SlugView.as_view()),
    path('', SlugView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
