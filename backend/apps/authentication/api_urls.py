from django.urls import path
from . import views

urlpatterns = [
    path('voice-check/', views.api_check_voice_user, name='voice_check'),
]

try:
    from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
    urlpatterns += [
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    ]
except ImportError:
    pass
