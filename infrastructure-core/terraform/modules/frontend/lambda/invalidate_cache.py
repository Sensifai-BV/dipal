import json
import boto3
import os

cloudfront = boto3.client('cloudfront')
DISTRIBUTION_ID = os.environ['DISTRIBUTION_ID']

def handler(event, context):
    """Invalidate CloudFront cache after deployment"""
    try:
        print(f"Creating invalidation for distribution {DISTRIBUTION_ID}")

        response = cloudfront.create_invalidation(
            DistributionId=DISTRIBUTION_ID,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 1,
                    'Items': ['/*']  # Invalidate all paths
                },
                'CallerReference': str(context.request_id)
            }
        )

        print(f"Invalidation created: {response['Invalidation']['Id']}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'CloudFront invalidation created',
                'invalidation_id': response['Invalidation']['Id']
            })
        }
    except Exception as e:
        print(f"Error creating invalidation: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
