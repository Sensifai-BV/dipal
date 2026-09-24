import requests
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings


class AIServiceAdapter:

    def start_job(self, job_id, input_path):
        url = f"{settings.AI_SERVICE_URL}/jobs/run"
        payload = {
            "job_id": job_id,
            "input_s3_path": input_path,
            "callback_url": f"{settings.BACKEND_URL}/v1/api/processing/callback/"
        }
        # In production use appropriate timeouts and headers
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.json()
        except requests.RequestException:
            return {"success": False, "message": "Connection error"}


class SocketNotificationService:

    @staticmethod
    def send_status_update(result_id, status, progress, outputs=None):
        channel_layer = get_channel_layer()
        group_name = f"processing_{result_id}"

        message = {
            "type": "processing_update",
            "data": {
                "job_id": str(result_id),
                "status": status,
                "progress": progress,
                "outputs": outputs
            }
        }

        async_to_sync(channel_layer.group_send)(group_name, message)
