from django.shortcuts import render
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets

from .models import ReferralCode
from .serializers import ReferralCodeSerializer, RegisterSerializer, MyTokenObtainPairSerializer
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache


class ReferralCodeViewSet(viewsets.ModelViewSet):
    queryset = ReferralCode.objects.all()
    serializer_class = ReferralCodeSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Создание нового реферального кода для аутентифицированного пользователя. Если код уже существует, вернется ошибка.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['code', 'expiration_date'],
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='Реферальный код'),
                'expiration_date': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME,
                                                  description='Дата истечения кода'),
            },
            example={
                'code': 'ABC123',
                'expiration_date': '2024-12-31T23:59:59Z'
            }
        ),
        responses={
            201: openapi.Response(
                description="Реферальный код успешно создан",
                examples={
                    "application/json": {
                        "id": 1,
                        "code": "ABC123",
                        "expiration_date": "2024-12-31T23:59:59Z"
                    }
                }
            ),
            400: openapi.Response(
                description="Ошибка создания реферального кода",
                examples={
                    "application/json": {
                        "error": "У вас уже есть активный реферальный код."
                    }
                }
            ),
        }
    )
    def create(self, request, *args, **kwargs):
        user = request.user

        if ReferralCode.objects.filter(user=user).exists():
            return Response({"error": "У вас уже есть активный реферальный код."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)

            cache.set(f'referral_code_{user.id}', serializer.data.referral_code, timeout=60 * 60 * 24)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Удаление существующего реферального кода пользователя.",
        responses={
            204: openapi.Response(description="Реферальный код успешно удален"),
            404: openapi.Response(description="Реферальный код не найден")
        }
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        cache.delete(f'referral_code_{instance.user.id}')

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    model = User
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Регистрация нового пользователя",
        request_body=RegisterSerializer,
        responses={201: 'Пользователь создан', 400: 'Ошибка в запросе'}
    )
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        referral_code = request.data.get('referral_code')

        if not username or not password or not email:
            return Response({'error': "Пожалуйста, предоставьте имя пользователя, пароль и email."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = User(username=username, email=email)
        user.set_password(password)
        user.save()

        if referral_code:
            try:
                referral = ReferralCode.objects.get(code=referral_code)
            except ReferralCode.DoesNotExist:
                return Response({"error": "Неверный реферальный код."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Пользователь успешно зарегистрирован."}, status=status.HTTP_201_CREATED)


class TokenObtainPairView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = MyTokenObtainPairSerializer

    @swagger_auto_schema(
        operation_description="Получение JWT-токена для аутентификации пользователя.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Имя пользователя'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Пароль'),
            },
            example={
                'username': 'user1',
                'password': 'password123'
            }
        ),
        responses={
            200: openapi.Response(
                description="Токены успешно выданы",
                examples={
                    "application/json": {
                        "refresh": "refresh_token_example",
                        "access": "access_token_example"
                    }
                }
            ),
            401: openapi.Response(
                description="Неверные учетные данные",
                examples={
                    "application/json": {
                        "error": "Неверные учетные данные."
                    }
                }
            ),
        }
    )
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = User.objects.filter(username=username).first()

        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })

        return Response({"error": "Неверные учетные данные."}, status=status.HTTP_401_UNAUTHORIZED)


class GetReferralCodeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReferralCodeSerializer

    @swagger_auto_schema(
        operation_description="Получение реферального кода по email",
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_QUERY, description="Email реферера", type=openapi.TYPE_STRING)],
        responses={
            200: openapi.Response(description="Реферальный код",
                                  examples={"application/json": {"referral_code": "ABC123"}}),
            404: 'Реферальный код не найден'
        }
    )
    def get(self, request, *args, **kwargs):
        email = request.query_params.get('email')
        try:
            cached_code = cache.get(f'referral_code_{email}')
            if cached_code:
                return Response({"referral_code": cached_code}, status=status.HTTP_200_OK)

            referral_code = ReferralCode.objects.get(user__email=email)
            cache.set(f'referral_code_{referral_code.user.id}', referral_code.code, timeout=60 * 60 * 24)

            return Response({"referral_code": referral_code.code}, status=status.HTTP_200_OK)
        except ReferralCode.DoesNotExist:
            return Response({"error": "Реферальный код не найден для данного email."}, status=status.HTTP_404_NOT_FOUND)
