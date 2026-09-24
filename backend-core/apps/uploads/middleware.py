from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

User = get_user_model()


@database_sync_to_async
def get_user(token_key):
    try:

        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        user = User.objects.get(id=user_id)
        print(f" JWT Auth Success: User {user.username} found.")
        return user
    except (InvalidToken, TokenError) as e:
        print(f" JWT Error: Invalid Token - {e}")
        return AnonymousUser()
    except User.DoesNotExist:
        print(f" JWT Error: User not found in DB.")
        return AnonymousUser()
    except Exception as e:
        print(f" JWT Unknown Error: {e}")
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):

        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)


        token = query_params.get("token", [None])[0]

        if token:
            print(f"🔎 Token received in URL: {token[:10]}...")
            scope["user"] = await get_user(token)
        else:
            print("⚠️ No token provided in URL.")
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
