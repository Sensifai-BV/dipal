import hmac
import hashlib

class WebhookService:
    @staticmethod
    def generate_signature(secret: str, payload: str) -> str:
        if not secret:
            return ""
        return hmac.new(
            key=secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
