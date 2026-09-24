import json
import boto3
import os
import base64
import zipfile
import io
import hmac
import hashlib

s3 = boto3.client('s3')
secrets_manager = boto3.client('secretsmanager')
lambda_client = boto3.client('lambda')

S3_BUCKET = os.environ['S3_BUCKET']
API_KEY_SECRET = os.environ['API_KEY_SECRET']
TELEGRAM_LAMBDA_ARN = os.environ.get('TELEGRAM_LAMBDA_ARN', '')

def send_telegram_notification(commit_sha, commit_message, author, branch, repository):
    """Send notification to Telegram via Lambda invocation"""
    if not TELEGRAM_LAMBDA_ARN:
        print("Telegram Lambda ARN not configured, skipping notification")
        return

    try:
        notification_payload = {
            'event_type': 'webhook',
            'detail': {
                'pipeline_type': 'Backend',
                'repository': repository,
                'branch': branch,
                'commit_sha': commit_sha,
                'commit_message': commit_message,
                'author': author
            }
        }

        lambda_client.invoke(
            FunctionName=TELEGRAM_LAMBDA_ARN,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(notification_payload)
        )
        print(f"Telegram notification sent for commit {commit_sha}")
    except Exception as e:
        print(f"Failed to send Telegram notification: {str(e)}")
        # Don't fail the webhook processing if notification fails

def handler(event, context):
    """
    Process GitLab webhook and trigger CodePipeline by uploading source to S3.
    """
    try:
        # Parse request
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

        # Parse GitLab webhook payload
        payload = json.loads(body)

        # Extract commit information
        event_name = payload.get('event_name', '')
        project = payload.get('project', {})
        repository = payload.get('repository', {})

        if event_name != 'push':
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event ignored (not a push event)'})
            }

        # Get the latest commit
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

        # Get repository details
        repo_url = repository.get('git_http_url', '')
        repo_name = repository.get('name', 'unknown')
        branch = payload.get('ref', '').replace('refs/heads/', '')

        # Create a simple metadata file
        metadata = {
            'commit_sha': commit_sha,
            'commit_message': commit_message,
            'repository_url': repo_url,
            'event_name': event_name
        }

        # Create a zip file with metadata
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))
            # Add a simple README for the source
            zip_file.writestr('README.txt', f'''
This archive was created by GitLab webhook.

Repository: {repo_url}
Commit: {commit_sha}
Message: {commit_message}

The actual source code should be cloned from the repository during the build process.
''')

        # Upload to S3 to trigger pipeline
        zip_buffer.seek(0)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key='source.zip',
            Body=zip_buffer.getvalue(),
            Metadata={
                'commit-sha': commit_sha,
                'repository-url': repo_url
            }
        )

        # Send Telegram notification
        send_telegram_notification(
            commit_sha=commit_sha,
            commit_message=commit_message,
            author=commit_author,
            branch=branch,
            repository=repo_name
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Webhook processed successfully',
                'commit': commit_sha
            })
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON payload'})
        }
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
