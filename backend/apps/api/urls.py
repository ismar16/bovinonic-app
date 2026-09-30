from django.urls import path

from .views_auth import LoginView, LogoutView, MeView, RefreshView
from .views_sync import SyncBatchView, SyncPullView

urlpatterns = [
    path("auth/login", LoginView.as_view()),
    path("auth/refresh", RefreshView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("auth/me", MeView.as_view()),
    path("sync/pull", SyncPullView.as_view()),
    path("sync/batch", SyncBatchView.as_view()),
]
