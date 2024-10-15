from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReferralCodeViewSet, TokenObtainPairView, RegisterView, GetReferralCodeView

router = DefaultRouter()
router.register(r'referral_codes', ReferralCodeViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('get_referral_code/', GetReferralCodeView.as_view(), name='get_referral_code'),
]