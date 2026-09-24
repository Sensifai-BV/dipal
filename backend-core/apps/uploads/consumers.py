import json
from channels.generic.websocket import AsyncWebsocketConsumer


class DatasetNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):

        self.user = self.scope.get("user")

        print(f"DEBUG: Connecting User: {self.user}")


        if self.user is None or self.user.is_anonymous:
            print("Unauthorized connection attempt. Closing.")
            await self.close(code=4001)
            return

        self.dataset_id = self.scope['url_route']['kwargs']['dataset_id']
        self.group_name = f"dataset_{self.dataset_id}"

        print(f"🔌 [DEBUG-CONSUMER] Frontend CONNECTED to: {self.group_name}")

        try:
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
            print(f" WebSocket Connected: {self.group_name} | User: {self.user.id}")

        except Exception as e:
            print(f" Critical Error: Could not connect to Channel Layer (Redis?): {e}")
            await self.close()

    async def disconnect(self, close_code):

        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        print(f"WebSocket Disconnected: Code {close_code}")

    async def send_update(self, event):
        print(f"DEBUG: Message received in Consumer! Payload: {event}")
        data = event['data']
        await self.send(text_data=json.dumps(data))
