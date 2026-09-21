# main/urls.py
from django.contrib import admin
from django.urls import path, re_path
from django.contrib.sitemaps.views import sitemap
from main.views import (
    LoginView, SignupView, LogoutView,
    PasswordResetRequestView, PasswordResetView,
    SlugCreateView, SlugEditView, SlugDeleteView, SlugView,
    SlugDynamicCreateView, SlugDynamicEditView,
    ProfileView, SendEmailView, ValidateView, ActivateAccountView, EditPasswordView,
    StaffUserListView, StaffUserCreateView, StaffUserEditView, StaffUserDeleteView,
    StaffUserSendValidationEmailView, StaffUserSendResetPasswordView, StaffTeamRolesApiView,
    StaffRoleListView, StaffDepartmentCreateView, StaffDepartmentEditView, StaffDepartmentDeleteView,
    StaffRoleCreateView, StaffRoleEditView, StaffRoleDeleteView,
    MyTeamView, MyTeamRemoveView,
    SubscribeView, ConfirmSubscriptionView, UnsubscribeView,
    robots_txt
)
from main.views.wiki import WikiRootCreateView, WikiPageCreateView, WikiPageEditView
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
    path('activate/<uuid:token>/', ActivateAccountView.as_view(), name='activate_account'),

    # Password Reset routes
    path('generate-prt/', PasswordResetRequestView.as_view(), name='generate_prt'),
    path('reset-password/<uuid:token>/', PasswordResetView.as_view(), name='reset_password'),

    # Core staff console: system-user management (see main/views/staff.py)
    path('staff/users/', StaffUserListView.as_view(), name='staff_user_list'),
    path('staff/users/create/', StaffUserCreateView.as_view(), name='staff_user_create'),
    path('staff/users/<uuid:pk>/edit/', StaffUserEditView.as_view(), name='staff_user_edit'),
    path('staff/users/<uuid:pk>/delete/', StaffUserDeleteView.as_view(), name='staff_user_delete'),
    path('staff/users/<uuid:pk>/send-reset/',
         StaffUserSendResetPasswordView.as_view(), name='staff_user_send_reset'),
    path('staff/users/<uuid:pk>/send-validation/',
         StaffUserSendValidationEmailView.as_view(), name='staff_user_send_validation'),
    path('staff/api/team-roles/<int:team_id>/', StaffTeamRolesApiView.as_view(), name='staff_api_team_roles'),

    # Core staff console: RBAC structure management (see main/views/roles.py)
    # - departments (auth.Group) and titles (TeamRole) themselves, as
    # opposed to staff/users/ above which only ASSIGNS an existing title
    # to a user.
    path('staff/roles/', StaffRoleListView.as_view(), name='staff_role_list'),
    path('staff/roles/departments/create/', StaffDepartmentCreateView.as_view(), name='staff_department_create'),
    path('staff/roles/departments/<int:pk>/edit/', StaffDepartmentEditView.as_view(), name='staff_department_edit'),
    path('staff/roles/departments/<int:pk>/delete/',
         StaffDepartmentDeleteView.as_view(), name='staff_department_delete'),
    path('staff/roles/departments/<int:group_id>/titles/create/',
         StaffRoleCreateView.as_view(), name='staff_role_create'),
    path('staff/roles/titles/<uuid:pk>/edit/', StaffRoleEditView.as_view(), name='staff_role_edit'),
    path('staff/roles/titles/<uuid:pk>/delete/', StaffRoleDeleteView.as_view(), name='staff_role_delete'),

    # Manager self-service delegation (see main/views/team.py) - a
    # department Manager's own scoped add/remove-members page, as
    # opposed to the Executive-tier-only full console above.
    path('staff/my-team/', MyTeamView.as_view(), name='my_team'),
    path('staff/my-team/remove/<uuid:pk>/', MyTeamRemoveView.as_view(), name='my_team_remove'),

    # Generic subscribe/confirm/unsubscribe routes (see
    # main/views/subscription.py + main/models/subscription.py) - addressed
    # by ContentType app_label/model + object pk, so any app's model can be
    # subscribed to without these routes knowing anything about it.
    path('subscribe/<str:app_label>/<str:model>/<uuid:object_id>/', SubscribeView.as_view(), name='subscribe'),
    path('subscriptions/confirm/<uuid:token>/', ConfirmSubscriptionView.as_view(), name='confirm_subscription'),
    path('subscriptions/unsubscribe/<uuid:token>/', UnsubscribeView.as_view(), name='unsubscribe'),

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

    # Wiki routes (main/views/wiki.py) - wiki pages are plain Slugs
    # (Slug.wiki_root/wiki_body), rendered by SlugView's own catch-all
    # below the moment it resolves one; these are just the create/edit
    # actions, matched by suffix, so they MUST come before the catch-all
    # but can otherwise sit anywhere relative to it. The home page's
    # get_absolute_url() is special-cased to '/' (no path segment of its
    # own), so <path:...>/wiki/create/ etc can never match a wiki hung
    # directly off home - these three root-only patterns (no <path:...>
    # prefix at all) cover exactly that case.
    path('wiki/create/', WikiRootCreateView.as_view(), {'base_path': ''}, name='wiki_root_create_home'),
    path('create/', WikiPageCreateView.as_view(), {'base_path': ''}, name='wiki_page_create_home'),
    path('edit/', WikiPageEditView.as_view(), {'base_path': ''}, name='wiki_page_edit_home'),
    path('<path:base_path>/wiki/create/', WikiRootCreateView.as_view(), name='wiki_root_create'),
    path('<path:base_path>/create/', WikiPageCreateView.as_view(), name='wiki_page_create'),
    path('<path:base_path>/edit/', WikiPageEditView.as_view(), name='wiki_page_edit'),

    # Catch-all slug routes MUST stay at the very bottom
    path('<path:slug_path>/', SlugView.as_view()),
    path('', SlugView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
