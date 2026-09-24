import json
import os
import urllib3
from datetime import datetime
import boto3

http = urllib3.PoolManager()
secrets_manager = boto3.client('secretsmanager')

TELEGRAM_SECRET_ARN = os.environ['TELEGRAM_SECRET_ARN']
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'photogear')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')

# Cache credentials to minimize Secrets Manager calls
_credentials_cache = None

def get_telegram_credentials():
    """Retrieve Telegram credentials from Secrets Manager with caching"""
    global _credentials_cache

    if _credentials_cache:
        return _credentials_cache

    try:
        response = secrets_manager.get_secret_value(SecretId=TELEGRAM_SECRET_ARN)
        credentials = json.loads(response['SecretString'])
        _credentials_cache = credentials
        return credentials
    except Exception as e:
        print(f"Error retrieving Telegram credentials: {str(e)}")
        raise

def send_telegram_message(message, parse_mode='HTML'):
    """Send message to Telegram Bot API"""
    try:
        credentials = get_telegram_credentials()
        bot_token = credentials['bot_token']
        chat_id = credentials['chat_id']

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }

        encoded_data = json.dumps(payload).encode('utf-8')

        response = http.request(
            'POST',
            url,
            body=encoded_data,
            headers={'Content-Type': 'application/json'}
        )

        if response.status != 200:
            print(f"Telegram API error: {response.status} - {response.data.decode('utf-8')}")
            return False

        print(f"Message sent successfully to Telegram")
        return True

    except Exception as e:
        print(f"Error sending Telegram message: {str(e)}")
        return False

def format_timestamp(timestamp_str=None):
    """Format timestamp to readable format"""
    if timestamp_str:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

def handle_codepipeline_event(detail):
    """Handle CodePipeline state change events"""
    pipeline_name = detail.get('pipeline', 'Unknown')
    state = detail.get('state', 'Unknown')
    execution_id = detail.get('execution-id', 'N/A')

    # Determine if backend or frontend
    pipeline_type = 'Frontend' if 'frontend' in pipeline_name.lower() else 'Backend'

    # Format message based on state
    if state == 'STARTED':
        emoji = '🔄'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Pipeline Started"
    elif state == 'SUCCEEDED':
        emoji = '✅'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Pipeline Successful"
    elif state == 'FAILED':
        emoji = '❌'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Pipeline Failed"
    else:
        emoji = 'ℹ️'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Pipeline {state}"

    message = f"{emoji} <b>{title}</b>\n\n"
    message += f"Pipeline: <code>{pipeline_name}</code>\n"
    message += f"Execution ID: <code>{execution_id}</code>\n"
    message += f"Time: {format_timestamp()}"

    return message

def handle_codebuild_event(detail):
    """Handle CodeBuild state change events"""
    project_name = detail.get('project-name', 'Unknown')
    build_status = detail.get('build-status', 'Unknown')
    build_id = detail.get('build-id', 'N/A')

    # Determine if backend or frontend
    pipeline_type = 'Frontend' if 'frontend' in project_name.lower() else 'Backend'

    # Format message based on build status
    if build_status == 'IN_PROGRESS':
        emoji = '🔄'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Build Started"
    elif build_status == 'SUCCEEDED':
        emoji = '✅'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Build Successful"

        # Add duration if available
        duration = detail.get('additional-information', {}).get('phases', [])
        if duration:
            total_duration = 0
            for phase in duration:
                if 'duration-in-seconds' in phase:
                    total_duration += phase['duration-in-seconds']

            minutes = total_duration // 60
            seconds = total_duration % 60
            duration_str = f"\nDuration: {minutes}m {seconds}s"
        else:
            duration_str = ""
    elif build_status == 'FAILED':
        emoji = '❌'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Build Failed"
        duration_str = ""
    else:
        emoji = 'ℹ️'
        title = f"{pipeline_type} {ENVIRONMENT.title()} - Build {build_status}"
        duration_str = ""

    message = f"{emoji} <b>{title}</b>\n\n"
    message += f"Project: <code>{project_name}</code>\n"
    message += f"Build ID: <code>{build_id.split('/')[-1] if '/' in build_id else build_id}</code>"

    if build_status == 'SUCCEEDED':
        message += duration_str

    message += f"\nTime: {format_timestamp()}"

    # Add logs link for failures
    if build_status == 'FAILED':
        region = os.environ.get('AWS_REGION', 'eu-north-1')
        logs_url = f"https://console.aws.amazon.com/codesuite/codebuild/projects/{project_name}/history"
        message += f"\n\n<a href='{logs_url}'>View Logs</a>"

    return message

def handle_webhook_event(event_detail):
    """Handle webhook invocation events from webhook processor Lambdas"""
    repository = event_detail.get('repository', 'Unknown')
    branch = event_detail.get('branch', 'Unknown')
    commit_sha = event_detail.get('commit_sha', 'N/A')
    commit_message = event_detail.get('commit_message', 'N/A')
    author = event_detail.get('author', 'Unknown')
    pipeline_type = event_detail.get('pipeline_type', 'Unknown')

    emoji = '📥'
    title = f"{pipeline_type} {ENVIRONMENT.title()} - Webhook Received"

    message = f"{emoji} <b>{title}</b>\n\n"
    message += f"Repository: <code>{repository}</code>\n"
    message += f"Branch: <code>{branch}</code>\n"
    message += f"Commit: <code>{commit_sha[:8]}</code>\n"
    message += f"Message: \"{commit_message}\"\n"
    message += f"Author: {author}\n"
    message += f"Time: {format_timestamp()}"

    return message

def handle_deployment_event(event_detail):
    """Handle ECS deployment events"""
    service_name = event_detail.get('service', 'Unknown')
    deployment_status = event_detail.get('status', 'Unknown')

    if deployment_status == 'PRIMARY':
        emoji = '🚀'
        title = f"Backend {ENVIRONMENT.title()} - Deployment Started"
    elif deployment_status == 'COMPLETED':
        emoji = '✅'
        title = f"Backend {ENVIRONMENT.title()} - Deployment Successful"

        # Add health status
        desired_count = event_detail.get('desired-count', 0)
        running_count = event_detail.get('running-count', 0)
        health_status = '✅ Healthy' if desired_count == running_count else '⚠️ Degraded'
    else:
        emoji = 'ℹ️'
        title = f"Backend {ENVIRONMENT.title()} - Deployment {deployment_status}"
        health_status = None

    message = f"{emoji} <b>{title}</b>\n\n"
    message += f"Service: <code>{service_name}</code>\n"

    if health_status:
        message += f"Tasks Running: {running_count}/{desired_count}\n"
        message += f"Health Status: {health_status}\n"

    message += f"Time: {format_timestamp()}"

    return message

def handler(event, context):
    """Main Lambda handler"""
    try:
        print(f"Received event: {json.dumps(event)}")

        # Check if this is a direct invocation from webhook Lambda
        if 'event_type' in event and event['event_type'] == 'webhook':
            message = handle_webhook_event(event.get('detail', {}))
            send_telegram_message(message)
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Webhook notification sent'})
            }

        # EventBridge events have detail and detail-type
        detail_type = event.get('detail-type', '')
        detail = event.get('detail', {})

        message = None

        if 'CodePipeline Pipeline Execution State Change' in detail_type:
            message = handle_codepipeline_event(detail)
        elif 'CodeBuild Build State Change' in detail_type:
            message = handle_codebuild_event(detail)
        elif 'ECS Deployment State Change' in detail_type:
            message = handle_deployment_event(detail)
        else:
            print(f"Unknown event type: {detail_type}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event type not handled'})
            }

        if message:
            send_telegram_message(message)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Notification sent successfully'})
        }

    except Exception as e:
        print(f"Error handling event: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
