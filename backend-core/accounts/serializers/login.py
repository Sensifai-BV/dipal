from rest_framework import serializers


class AccountLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        min_length=8,
        max_length=32,
        write_only=True,
    )
