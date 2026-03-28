from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()


class JWTAuthentication(BaseJWTAuthentication):
    """
    Custom JWT authentication that extends simplejwt with debug mock-token support.
    """

    def authenticate(self, request):
        if settings.DEBUG:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token_str = auth_header.split(' ')[1]
                if token_str in ('console-token', 'mock-token', 'test-token'):
                    user, _ = User.objects.get_or_create(
                        email='dev@tabletap.com',
                        defaults={
                            'username': 'dev_user',
                            'first_name': 'Dev',
                            'last_name': 'User',
                            'is_verified': True,
                            'role': 'owner',
                        },
                    )
                    return (user, None)

        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError) as e:
            raise AuthenticationFailed(str(e))

    def authenticate_header(self, request):
        return 'Bearer'
