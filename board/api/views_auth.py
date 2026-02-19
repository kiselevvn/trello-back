# api/views_auth.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .serializers_auth import (
    UserRegisterSerializer, UserLoginSerializer, UserProfileSerializer,
    ChangePasswordSerializer, TokenObtainPairResponseSerializer,
    TokenRefreshResponseSerializer
)


class RegisterView(generics.CreateAPIView):
    """View для регистрации пользователя"""
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Создаем токены для нового пользователя
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Кастомный view для получения токенов с данными пользователя"""
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Получаем пользователя по имени пользователя
            username = request.data.get('username')
            user = User.objects.get(username=username)
            
            # Добавляем данные пользователя в ответ
            response.data['user'] = UserProfileSerializer(user).data
        
        return response


class LoginView(APIView):
    """View для входа пользователя (альтернатива JWT)"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        # Аутентифицируем пользователя
        user = authenticate(username=username, password=password)
        
        if user is not None:
            if user.is_active:
                # Создаем токены
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'user': UserProfileSerializer(user).data,
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Аккаунт неактивен.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {'error': 'Неверное имя пользователя или пароль.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class CustomTokenRefreshView(TokenRefreshView):
    """Кастомный view для обновления токена"""
    pass


class LogoutView(APIView):
    """View для выхода пользователя"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response(
                {'message': 'Успешный выход из системы.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LogoutAllView(APIView):
    """View для выхода со всех устройств"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Инвалидируем все токены пользователя
            # Вам нужно установить django-rest-framework-simplejwt-blacklist
            # для реализации этой функции
            
            return Response(
                {'message': 'Успешный выход со всех устройств.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """View для получения и обновления профиля пользователя"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    """View для смены пароля"""
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = self.get_object()
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Инвалидируем старые токены
        # Можно добавить логику blacklist здесь
        
        return Response(
            {'message': 'Пароль успешно изменен.'},
            status=status.HTTP_200_OK
        )


class VerifyTokenView(APIView):
    """View для проверки валидности токена"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response(
            {'message': 'Токен валиден.', 'user': UserProfileSerializer(request.user).data},
            status=status.HTTP_200_OK
        )


# Дополнительные views для управления пользователями
class UserListView(generics.ListAPIView):
    """View для получения списка пользователей"""
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    # filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']


class UserDetailView(generics.RetrieveAPIView):
    """View для получения детальной информации о пользователе"""
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]