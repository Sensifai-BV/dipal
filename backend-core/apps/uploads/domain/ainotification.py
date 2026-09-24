from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class DjangoChannelsNotificationService:
    def notify_frontend(self, dataset_id, message_type, payload):
        channel_layer = get_channel_layer()
        group_name = f"dataset_{dataset_id}"

        print(f"🔍 [DEBUG-SENDER] Try sending to Group: {group_name} | Type: {message_type}")
        print(f"🔍 [DEBUG-SENDER] Channel Layer Backend: {channel_layer}")

        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_update",
                    "data": {
                        "type": message_type,
                        "payload": payload
                    }
                }
            )
            print(f"Notification sent to group {group_name}: {message_type}")
        except Exception as e:
            print(f"Failed to send notification to {group_name}: {e}")
