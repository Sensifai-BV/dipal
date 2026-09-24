"""AI Gateway HTTP Client"""
import requests
import logging
from django.conf import settings
from typing import Dict, Any, Optional

from chromatrace.tracer import trace_id_ctx

logger = logging.getLogger(__name__)


class AIGatewayClient:
    """Client for communicating with AI Gateway"""
    
    def __init__(self):
        self.base_url = settings.AI_GATEWAY_URL
        self.secret_key = settings.AI_GATEWAY_SECRET_KEY
        self.timeout = 120  # Increased timeout for large datasets
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with trace ID forwarding"""
        headers = {
            "Content-Type": "application/json",
            "X-API-Secret-Key": self.secret_key,
        }
        trace_id = trace_id_ctx.get()
        if trace_id:
            headers["X-Request-ID"] = trace_id
        return headers
    
    def start_processing_job(
        self,
        job_id: str,
        dataset_id: str,
        download_url: str,
        parameters: Optional[Dict[str, Any]] = None,
        starting_stage: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit a processing job to AI Gateway
        
        Args:
            job_id: Backend job ID (will be used by AI Gateway)
            dataset_id: Dataset ID
            download_url: Presigned URL for downloading raw images
            parameters: Processing parameters (resolution_gsd, calibration, etc.)
            starting_stage: Stage to resume from (e.g., 'sfm', 'orthomosaic_generation')
            
        Returns:
            AI Gateway response with job status
        """
        url = f"{self.base_url}/jobs/run"
        
        payload = {
            "job_id": job_id,  # Pass backend job_id to AI Gateway (REQUIRED)
            "dataset_id": dataset_id,
            "download_url": download_url,
            "parameters": parameters or {}
        }
        
        # Add starting_stage if provided (for resuming from specific stage)
        if starting_stage:
            payload["starting_stage"] = starting_stage
        
        try:
            logger.info(f"Submitting job {job_id} to AI Gateway: {url}")
            logger.info(f"Payload: {payload}")
            
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"AI Gateway accepted job {job_id}. AI job_id: {result.get('job_id')}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to submit job to AI Gateway: {e}")
            raise Exception(f"AI Gateway communication error: {str(e)}")
    
    def get_job_status(self, ai_job_id: str) -> Dict[str, Any]:
        """
        Get job status from AI Gateway
        
        Args:
            ai_job_id: AI Gateway's job ID
            
        Returns:
            Job status information
        """
        url = f"{self.base_url}/jobs/{ai_job_id}/status"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to get job status from AI Gateway: {e}")
            raise Exception(f"AI Gateway communication error: {str(e)}")
    
    def cancel_job(self, ai_job_id: str) -> Dict[str, Any]:
        """
        Cancel a job in AI Gateway
        
        Args:
            ai_job_id: AI Gateway's job ID
            
        Returns:
            Cancellation confirmation
        """
        url = f"{self.base_url}/jobs/{ai_job_id}/cancel"
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to cancel job in AI Gateway: {e}")
            raise Exception(f"AI Gateway communication error: {str(e)}")
    
    def resume_job(self, job_id: str, stage: Optional[str] = None) -> Dict[str, Any]:
        """
        Resume a job in AI Gateway from a specific stage.
        
        Args:
            job_id: Job ID
            stage: Stage to resume from (optional, defaults to next stage after last completed)
            
        Returns:
            Resume confirmation with stage info
        """
        url = f"{self.base_url}/jobs/{job_id}/resume"
        params = {}
        if stage:
            params["stage"] = stage
        
        try:
            logger.info(f"Resuming job {job_id} at AI Gateway (stage={stage})")
            response = requests.post(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"AI Gateway resumed job {job_id}: {result}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to resume job in AI Gateway: {e}")
            raise Exception(f"AI Gateway communication error: {str(e)}")
