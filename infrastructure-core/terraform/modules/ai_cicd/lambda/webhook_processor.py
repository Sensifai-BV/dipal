import json
import boto3
import os
import base64
import zipfile
import io
import hmac
import re

s3 = boto3.client('s3')
secrets_manager = boto3.client('secretsmanager')
lambda_client = boto3.client('lambda')

S3_BUCKET = os.environ['S3_BUCKET']
API_KEY_SECRET = os.environ['API_KEY_SECRET']
TELEGRAM_LAMBDA_ARN = os.environ.get('TELEGRAM_LAMBDA_ARN', '')

# Service tag to S3 key mapping
SERVICE_MAP = {
    'api-gateway': 'ai-api-gateway-source.zip',
    'calibration': 'ai-calibration-source.zip',
    'sfm':         'ai-sfm-source.zip',
    'orthomosaic': 'ai-orthomosaic-source.zip',
}

TAG_PATTERN = re.compile(r'\[([\w-]+)\]')


def parse_service_tags(commit_message):
    """Extract service tags from commit message like [api-gateway] or [all]."""
    tags = TAG_PATTERN.findall(commit_message.lower())

    if 'all' in tags:
        return list(SERVICE_MAP.keys())

    return [t for t in tags if t in SERVICE_MAP]


def handler(event, context):
    try:
        headers = event.get('headers', {})
        body = event.get('body', '{}')

        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('utf-8')

        # Validate API key
        api_key = headers.get('x-api-key', '')

        try:
            secret_response = secrets_manager.get_secret_value(SecretId=API_KEY_SECRET)
            expected_api_key = secret_response['SecretString']
        except Exception as e:
            print(f"Error retrieving API key: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Internal server error'})
            }

        if not hmac.compare_digest(api_key, expected_api_key):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized'})
            }

        payload = json.loads(body)
        event_name = payload.get('event_name', '')

        if event_name != 'push':
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event ignored (not a push event)'})
            }

        commits = payload.get('commits', [])
        if not commits:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No commits found'})
            }

        latest_commit = commits[-1]
        commit_sha = latest_commit.get('id', '')
        commit_message = latest_commit.get('message', '')
        commit_author = latest_commit.get('author', {}).get('name', 'Unknown')

        repository = payload.get('repository', {})
        repo_url = repository.get('git_http_url', '')
        repo_name = repository.get('name', 'unknown')
        branch = payload.get('ref', '').replace('refs/heads/', '')

        # Parse service tags from commit message
        services = parse_service_tags(commit_message)

        if not services:
            print(f"No service tags found in commit message: {commit_message}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No service tags found. Use [api-gateway], [calibration], [sfm], [orthomosaic], or [all].',
                    'commit': commit_sha
                })
            }

        # Create metadata zip
        metadata = {
            'commit_sha': commit_sha,
            'commit_message': commit_message,
            'repository_url': repo_url,
            'branch': branch,
            'services_triggered': services
        }

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))

        zip_bytes = zip_buffer.getvalue()

        # Upload to S3 for each matched service
        triggered = []
        for service in services:
            source_key = SERVICE_MAP[service]
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=source_key,
                Body=zip_bytes,
                Metadata={
                    'commit-sha': commit_sha,
                    'service': service
                }
            )
            triggered.append(source_key)
            print(f"Uploaded {source_key} for service {service}")

        # Send Telegram notification
        if TELEGRAM_LAMBDA_ARN:
            try:
                lambda_client.invoke(
                    FunctionName=TELEGRAM_LAMBDA_ARN,
                    InvocationType='Event',
                    Payload=json.dumps({
                        'event_type': 'webhook',
                        'detail': {
                            'pipeline_type': 'AI Services',
                            'repository': repo_name,
                            'branch': branch,
                            'commit_sha': commit_sha,
                            'commit_message': commit_message,
                            'author': commit_author,
                            'services_triggered': services
                        }
                    })
                )
            except Exception as e:
                print(f"Failed to send Telegram notification: {str(e)}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'AI webhook processed',
                'commit': commit_sha,
                'services_triggered': services,
                'source_keys': triggered
            })
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON payload'})
        }
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
