from rest_framework import serializers
from apps.fmis.models import WebhookEndpoint, FMISIntegration, Job


class WebhookSerializer(serializers.ModelSerializer):
    events = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=False
    )
    headers = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = WebhookEndpoint
        fields = ['id', 'url', 'secret', 'events', 'active', 'headers', 'created_at']
        read_only_fields = ['id', 'created_at', 'secret']

    def validate_events(self, value):
        valid_events = [e[0] for e in WebhookEndpoint.AVAILABLE_EVENTS]
        for event in value:
            if event not in valid_events:
                raise serializers.ValidationError(f"Invalid event: {event}")
        return value


class FMISIntegrationSerializer(serializers.ModelSerializer):
    api_token = serializers.CharField(write_only=True)

    class Meta:
        model = FMISIntegration
        fields = [
            'id', 'provider_name', 'base_url', 'api_token', 'extra_headers',
            'status', 'last_connected_at', 'last_error_message'
        ]
        read_only_fields = ['id', 'status', 'last_connected_at', 'last_error_message']


class TestConnectionRequestSerializer(serializers.Serializer):
    provider_name = serializers.ChoiceField(choices=FMISIntegration.PROVIDER_CHOICES, default='generic')
    base_url = serializers.URLField()
    api_token = serializers.CharField()
    extra_headers = serializers.JSONField(required=False, default=dict)


# --- NEW SERIALIZER FOR JOBS ---
class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['id', 'input_data', 'result_data', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'result_data', 'status', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Automatically assign organization from request user
        user = self.context['request'].user
        validated_data['org'] = user.organization
        return super().create(validated_data)
