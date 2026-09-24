from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..infrastructure.repositories import DjangoTaskRepository
from ..infrastructure.services import HttpAIServiceClient, S3StorageService
from ..application.use_cases import RequestProcessingUseCase, ProcessWebhookUseCase

class ProcessingRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Dependencies
        repo = DjangoTaskRepository()
        ai_service = HttpAIServiceClient()
        storage = S3StorageService()
        use_case = RequestProcessingUseCase(repo, ai_service, storage)

        s3_key = request.data.get('s3_key')
        task_type = request.data.get('type') # '2D' or '3D'

        try:
            task = use_case.execute(request.user.id, s3_key, task_type)
            return Response({"task_id": task.id, "status": task.status}, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class WebhookView(APIView):
    def post(self, request):
        repo = DjangoTaskRepository()
        use_case = ProcessWebhookUseCase(repo)

        task_id = request.data.get('task_id')
        status_val = request.data.get('status')
        result = request.data.get('result', {})
        error = request.data.get('error', None)

        try:
            use_case.execute(task_id, status_val, result, error)
            return Response({"msg": "Webhook received"}, status=status.HTTP_200_OK)
        except Exception as e:
            # Log this error
            return Response({"error": "Task not found or update failed"}, status=status.HTTP_404_NOT_FOUND)
