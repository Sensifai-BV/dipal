import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db import transaction

from chromatrace.tracer import trace_id_ctx

from ..infrastructure.models import AIProcessingJob, AIResultFile, UploadStatus
from ..domain.constants import UploadStatusName


class AIService:

    @staticmethod
    @transaction.atomic
    def process_callback(data):
        job_id = data.get('job_id')
        status_name = data.get('status')
        files_data = data.get('files', [])


        job = get_object_or_404(AIProcessingJob, id=job_id)

        status_obj = get_object_or_404(UploadStatus, name=status_name)


        job.status = status_name
        job.save()


        if status_obj.name == UploadStatusName.COMPLETED:
            results = []
            for f in files_data:
                results.append(AIResultFile(
                    job=job,
                    file_name=f.get('file_name'),
                    s3_key=f.get('s3_key'),
                    file_type=f.get('file_type')
                ))
            AIResultFile.objects.bulk_create(results)


        elif status_obj.name == UploadStatusName.FAILED:
            pass

        return job


    @staticmethod
    def trigger_ai_processing(job_id, dataset_id, download_url, metadata=None):

        ai_endpoint = getattr(settings, 'AI_SERVICE_ENDPOINT', "https://ai-team-server.com/api/start-process/")
        api_key = getattr(settings, 'AI_SERVICE_API_KEY', "test-key")

        payload = {
            "job_id": str(job_id),
            "dataset_id": str(dataset_id),
            "file_url": download_url,
            "metadata": metadata or {}
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        trace_id = trace_id_ctx.get()
        if trace_id:
            headers["X-Request-ID"] = trace_id

        try:
            response = requests.post(ai_endpoint, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"AI Service Error: {e}")
            raise ConnectionError(f"Failed to connect to AI Service: {str(e)}")