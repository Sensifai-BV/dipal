import os
import uuid
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from ..infrastructure.models import UploadStatus
from .pagination import StandardResultsSetPagination
from config.logging_config import get_logger

logger = get_logger(__name__)


from ..application.use_cases import (
    GetUserUploadsUseCase,
    GetUserDatasetsStatsUseCase
)
from ..application.multipart_use_cases import (
    InitiateMultipartUploadUseCase,
    SignMultipartPartUseCase,
    CompleteMultipartUploadUseCase,
    AbortAndRetryMultipartUploadUseCase
)
from ..application.uri_upload_use_casees import (
    StartUploadFromUrlUseCase,
)
from .serializers import (
    ImageSerializer,
    DatasetStatsSerializer,
    UploadStatusSerializer,
    InitMultipartRequestSerializer,
    InitMultipartResponseSerializer,
    SignPartRequestSerializer,
    SignPartResponseSerializer,
    CompleteMultipartRequestSerializer,
    RetryMultipartUploadRequestSerializer,
    UploadFromUrlRequestSerializer,
    UploadFromUrlResponseSerializer
)
from ..Tasks.urluploadtasks import download_and_process_url_task


class InitiateMultipartUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Step 1: Start Upload Session",
        description="""
        **Call this FIRST.**
        It creates a record in the database and initializes a Multipart Upload session with S3.

        **Returns:**
        - `upload_id`: You need this for the next steps.
        - `s3_key`: Where the file will be stored.
        """,
        tags=['Upload Flow (Multipart)'],
        request=InitMultipartRequestSerializer,
        responses={200: InitMultipartResponseSerializer},
        examples=[
            OpenApiExample(
                'Start Zip Upload',
                summary='Initialize 5GB Zip Upload',
                description='Example payload for starting a large dataset upload.',
                value={
                    "dataset_name": "My New Dataset",
                    "batch_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "file_name": "dataset_v1.zip",
                    "file_type": "ARCHIVE",
                    "content_type": "application/zip",
                    "file_size": 5368709120
                }
            )
        ]
    )
    def post(self, request):
        logger.info(f"[MULTIPART-INIT] Received init request from user {request.user.id}")
        logger.debug(f"[MULTIPART-INIT] Request data keys: {list(request.data.keys())}")
        
        serializer = InitMultipartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org_id = getattr(request.user, 'organization_id', 1)
        
        logger.info(
            f"[MULTIPART-INIT] Starting upload - file: {data['file_name']}, "
            f"size: {data['file_size']} bytes ({data['file_size']/1024/1024:.2f} MB), "
            f"type: {data['file_type']}, content_type: {data['content_type']}, "
            f"user_id: {request.user.id}, org_id: {org_id}"
        )

        use_case = InitiateMultipartUploadUseCase()
        try:
            result_entity = use_case.execute(
                user_id=request.user.id,
                organization_id=org_id,
                dataset_name=data.get('dataset_name'),
                dataset_id=data.get('dataset_id'),
                batch_id=data['batch_id'],
                file_name=data['file_name'],
                file_type=data['file_type'],
                content_type=data['content_type'],
                file_size=data['file_size']
            )
            
            logger.info(
                f"[MULTIPART-INIT] ✅ SUCCESS - upload_id: {result_entity.id}, "
                f"s3_upload_id: {getattr(result_entity, 's3_upload_id', 'N/A')}, "
                f"s3_key: {result_entity.s3_key}, dataset_id: {result_entity.dataset_id}"
            )
            logger.info(
                f"[MULTIPART-INIT] Next step: Frontend should call sign-part endpoint "
                f"with upload_id={result_entity.id} for each chunk"
            )

            return Response({
                "upload_id": result_entity.id,
                "s3_upload_id": getattr(result_entity, 's3_upload_id', ''),
                "s3_key": result_entity.s3_key,
                "dataset_id": result_entity.dataset_id
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"[MULTIPART-INIT] ❌ FAILED - file: {data['file_name']}, "
                f"user_id: {request.user.id}, error: {str(e)}",
                exc_info=True
            )
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SignMultipartPartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Step 2: Get URL for a Part",
        description="""
        **Call this in a Loop.**
        The frontend must split the file into chunks (e.g., 10MB each).
        For EACH chunk, call this endpoint to get a presigned URL.

        **Flow:**
        1. Frontend splits file -> Part 1, Part 2...
        2. Call this endpoint for Part 1 -> Get URL -> PUT binary data to that URL.
        3. Save the `ETag` header from S3 response.
        4. Repeat for all parts.
        """,
        tags=['Upload Flow (Multipart)'],
        request=SignPartRequestSerializer,
        responses={200: {'type': 'object', 'properties': {'url': {'type': 'string'}}}},
        examples=[
            OpenApiExample(
                'Sign Part 1',
                value={
                    "upload_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "part_number": 1
                }
            )
        ]
    )
    def post(self, request):
        logger.info(
            f"[MULTIPART-SIGN] Received sign-part request - "
            f"upload_id: {request.data.get('upload_id')}, "
            f"part_number: {request.data.get('part_number')}, "
            f"user_id: {request.user.id}"
        )
        
        serializer = SignPartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = SignMultipartPartUseCase()
        try:
            logger.debug(
                f"[MULTIPART-SIGN] Generating presigned URL for upload_id: {data['upload_id']}, "
                f"part: {data['part_number']}"
            )
            # This url will now have 24h expiry based on S3Service update
            url = use_case.execute(
                upload_db_id=data['upload_id'],
                part_number=data['part_number']
            )
            
            logger.info(
                f"[MULTIPART-SIGN] ✅ SUCCESS - Generated presigned URL for upload_id: {data['upload_id']}, "
                f"part: {data['part_number']}, URL length: {len(url)}"
            )
            logger.debug(f"[MULTIPART-SIGN] Presigned URL (truncated): {url[:100]}...")
            logger.info(
                f"[MULTIPART-SIGN] Next step: Frontend should PUT chunk {data['part_number']} "
                f"to this URL and save the ETag from response headers"
            )
            
            return Response({"url": url}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"[MULTIPART-SIGN] ❌ FAILED - upload_id: {data['upload_id']}, "
                f"part: {data['part_number']}, error: {str(e)}",
                exc_info=True
            )
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompleteMultipartUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Step 3: Finish Upload",
        description="""
        **Call this LAST.**
        Once all parts are uploaded to S3, send the list of parts (PartNumber and ETag) here.
        This merges the file in S3 and triggers the extraction task (Celery).
        """,
        tags=['Upload Flow (Multipart)'],
        request=CompleteMultipartRequestSerializer,
        responses={200: ImageSerializer},
        examples=[
            OpenApiExample(
                'Complete Upload Payload',
                value={
                    "upload_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "parts": [
                        {"PartNumber": 1, "ETag": "\"a1b2c3...\""},
                        {"PartNumber": 2, "ETag": "\"d4e5f6...\""}
                    ]
                }
            )
        ]
    )
    def post(self, request):
        upload_id = request.data.get('upload_id')
        parts_count = len(request.data.get('parts', []))
        
        logger.info(
            f"[MULTIPART-COMPLETE] Received complete request - "
            f"upload_id: {upload_id}, parts_count: {parts_count}, "
            f"user_id: {request.user.id}"
        )
        logger.debug(f"[MULTIPART-COMPLETE] Parts summary: {[p.get('PartNumber') for p in request.data.get('parts', [])]}")
        
        serializer = CompleteMultipartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = CompleteMultipartUploadUseCase()
        try:
            logger.info(f"[MULTIPART-COMPLETE] Executing complete for upload_id: {data['upload_id']}")
            
            entity = use_case.execute(
                upload_db_id=data['upload_id'],
                parts=data['parts']
            )
            
            logger.info(
                f"[MULTIPART-COMPLETE] ✅ SUCCESS - upload_id: {data['upload_id']}, "
                f"file: {entity.file_name}, status: {entity.status}, "
                f"s3_key: {entity.s3_key}"
            )
            
            if entity.file_type == 'ARCHIVE':
                logger.info(
                    f"[MULTIPART-COMPLETE] Archive detected - Celery task triggered for extraction. "
                    f"Upload status set to PROCESSING."
                )
            else:
                logger.info(f"[MULTIPART-COMPLETE] Non-archive file - Status set to COMPLETED")
            
            return Response(ImageSerializer(entity).data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"[MULTIPART-COMPLETE] ❌ FAILED - upload_id: {data['upload_id']}, "
                f"parts_count: {len(data['parts'])}, error: {str(e)}",
                exc_info=True
            )
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RetryMultipartUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_case = AbortAndRetryMultipartUploadUseCase()

    @extend_schema(
        summary="Retry Full Upload Session",
        description="Use this if the entire upload session is stale or broken (not just a single part). It aborts the old S3 multipart ID and creates a new one for the same file record.",
        request=RetryMultipartUploadRequestSerializer,
        responses={200: InitMultipartResponseSerializer},
        tags=['Uploads - Flow']
    )
    def post(self, request):
        serializer = RetryMultipartUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            # result should contain: upload_id, s3_upload_id, s3_key
            result = self.use_case.execute(
                upload_db_id=data['upload_id'],
                user_id=request.user.id
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------
#  Upload From S3 URL (Import)
# ---------------------------------------------------------

class UploadFromUrlView(APIView):


    @extend_schema(
        summary="Import from S3 URL",
        description="Server copies file from external S3 bucket. Supports cross-bucket auth via access_key/secret_key.",
        request=UploadFromUrlRequestSerializer,
        responses={
            202: {'type': 'object', 'properties': {'upload_id': {'type': 'string'}, 'status': {'type': 'string'}, 'message': {'type': 'string'}}}
        },
        tags=['Uploads-URL']
    )

    def post(self, request):
        serializer = UploadFromUrlRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org_id = getattr(request.user, 'organization_id', 1)
        file_url = data['file_url']

        final_file_name = data.get('file_name')
        if not final_file_name:
            clean_url = file_url.split('?')[0]
            final_file_name = clean_url.split('/')[-1]

            if not final_file_name:
                final_file_name = f"import_{uuid.uuid4().hex[:6]}.zip"

        batch_id = data.get('batch_id') or uuid.uuid4()

        logger.info(
            f"[URL_UPLOAD] Starting URL import for user={request.user.id}, "
            f"org={org_id}, file={final_file_name}"
        )

        use_case = StartUploadFromUrlUseCase()
        try:
            result_entity = use_case.execute(
                user_id=request.user.id,
                organization_id=org_id,
                dataset_name=data.get('dataset_name'),
                dataset_id=data.get('dataset_id'),
                batch_id=batch_id,
                file_url=file_url,
                file_name=final_file_name
            )

            logger.info(
                f"[URL_UPLOAD] Upload record created: upload_id={result_entity.id}, "
                f"dataset_id={result_entity.dataset_id}, s3_key={result_entity.s3_key}"
            )

            download_and_process_url_task.delay(
                upload_id=str(result_entity.id),
                file_url=file_url,
                s3_key=result_entity.s3_key,
            )

            logger.info(f"[URL_UPLOAD] Background download task queued for upload_id={result_entity.id}")

            return Response({
                "upload_id": result_entity.id,
                "dataset_id": result_entity.dataset_id,
                "status": "DOWNLOADING",
                "message": f"Start downloading '{final_file_name}' in background."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            logger.error(f"[URL_UPLOAD] Failed to start URL import: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------
#  Read / Stats Views
# ---------------------------------------------------------

class UserUploadsView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.get_uploads_use_case = GetUserUploadsUseCase()

    @extend_schema(
        summary="List My Uploads",
        description="Get a history of uploads. Useful for checking status (PENDING -> COMPLETED).",
        parameters=[
            OpenApiParameter(name='dataset_id', type=OpenApiTypes.UUID, location=OpenApiParameter.QUERY,
                             description="Filter by Dataset"),
            OpenApiParameter(name='batch_id', type=OpenApiTypes.UUID, location=OpenApiParameter.QUERY,
                             description="Filter by Upload Batch"),
            OpenApiParameter(name='file_type', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                             description="Filter by file type (IMAGE or ARCHIVE)", 
                             enum=['IMAGE', 'ARCHIVE']),
            OpenApiParameter(name='page', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                             description="Page number"),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                             description="Items per page"),
        ],
        responses={200: ImageSerializer(many=True)},
        tags=['Uploads - Status & Management']
    )
    def get(self, request):
        dataset_id_str = request.query_params.get('dataset_id')
        batch_id_str = request.query_params.get('batch_id')
        file_type = request.query_params.get('file_type')

        dataset_id = uuid.UUID(dataset_id_str) if dataset_id_str else None
        batch_id = uuid.UUID(batch_id_str) if batch_id_str else None

        uploads_entities = self.get_uploads_use_case.execute(
            user_id=request.user.id,
            dataset_id=dataset_id,
            batch_id=batch_id,
            file_type=file_type
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(uploads_entities, request, view=self)

        if page is not None:
            serializer = ImageSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ImageSerializer(uploads_entities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserDatasetsStatsView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_case = GetUserDatasetsStatsUseCase()

    @extend_schema(
        summary="Get All Datasets",
        description="Returns list of datasets with total file count and size.",
        parameters=[
            OpenApiParameter(name='page', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        ],
        responses={200: DatasetStatsSerializer(many=True)},
        tags=['Uploads - Status & Management']
    )
    def get(self, request):
        stats = self.use_case.execute(user_id=request.user.id)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(stats, request, view=self)

        if page is not None:
            serializer = DatasetStatsSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = DatasetStatsSerializer(stats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UploadStatusListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = UploadStatus.objects.all().order_by('id')
    serializer_class = UploadStatusSerializer

    @extend_schema(
        summary="Get All Possible Statuses",
        tags=['Uploads - Read']
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class DatasetExportStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Check Dataset Archive Status",
        description="Checks the database for the status of the .zip (ARCHIVE) file associated with this dataset.",
        parameters=[
            OpenApiParameter(name='dataset_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Uploads - Read']
    )
    def get(self, request, dataset_id):
        archive_info = UploadRepository.get_dataset_archive_status(dataset_id)

        if not archive_info:
            return Response({
                'status': 'NOT_FOUND',
                'message': 'No archive (.zip) file found for this dataset.'
            }, status=status.HTTP_404_NOT_FOUND)

        response_data = {
            'dataset_id': dataset_id,
            'file_name': archive_info['file_name'],
            'status': archive_info['status'],
            'label': archive_info['status_label'],
            'updated_at': archive_info['updated_at']
        }

        return Response(response_data, status=status.HTTP_200_OK)