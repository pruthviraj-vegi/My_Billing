from django.urls import path
from . import views

app_name = "user"

urlpatterns = [
    path("", views.home, name="home"),
    path("download/", views.download_users, name="download"),
    path("create/", views.CreateUser.as_view(), name="create"),
    path("sessions/", views.sessions_overview, name="sessions"),
    path(
        "sessions/invalidate/all/",
        views.invalidate_all_sessions,
        name="invalidate_all_sessions",
    ),
    path(
        "sessions/invalidate/<str:session_key>/",
        views.invalidate_session,
        name="invalidate_session",
    ),
    path("logins/", views.logins_overview, name="logins"),
    path("logins/download/", views.download_logins, name="logins_download"),
    path("<int:pk>/", views.user_detail, name="detail"),
    path("<int:pk>/edit/", views.EditUser.as_view(), name="edit"),
    path("<int:pk>/delete/", views.DeleteUser.as_view(), name="delete"),
    path("<int:user_id>/status/", views.change_user_status, name="change_status"),
    path(
        "<int:user_id>/reset-password/",
        views.reset_user_password,
        name="reset_password",
    ),
]
