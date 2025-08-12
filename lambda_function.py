import boto3
import json
import cfnresponse
from botocore.config import Config
import traceback

def get_boto3_config() -> Config:
    return Config(
        user_agent_extra="team-idc"
    )

amplify = boto3.client('amplify')
s3 = boto3.client('s3', config=get_boto3_config())

policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowSSLRequestsOnly",
            "Principal": {
                "AWS": "*"
            },
            "Effect": "Deny",
            "Action": ["s3:*"],
            "Resource": [
                "arn:aws:s3:::AMPLIFY_BUCKET",
                "arn:aws:s3:::AMPLIFY_BUCKET/*"
            ],
            "Condition": {
                "Bool": {
                    "aws:SecureTransport": False
                }
            }
        }
    ]
}

def handler(event, context):
    responseData = {}
    responseData['Data'] = "Failure"
    
    try:
        print(f"Event: {json.dumps(event)}")
        
        if event['RequestType'] == 'Delete':
            print("Delete request - skipping")
            responseData['Data'] = "Success"
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
            return
        
        response = amplify.list_apps()
        print(f"Available apps: {[app['name'] for app in response['apps']]}")
        
        app_id = None
        for app in response["apps"]:
            if "team" in app["name"].lower() or "idc" in app["name"].lower():
                app_id = app['appId']
                print(f"Found matching app: {app['name']} with ID: {app_id}")
                break
        
        if not app_id:
            print("No matching Amplify app found")
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData)
            return
        
        backend_env = amplify.get_backend_environment(appId=app_id, environmentName='main')
        stackName = backend_env['backendEnvironment']['stackName']
        amplifyBucket = f"{stackName}-deployment"
        
        print(f"Amplify bucket name: {amplifyBucket}")
        
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=amplifyBucket)
        except Exception as e:
            print(f"Bucket {amplifyBucket} not found: {e}")
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData)
            return
        
        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=amplifyBucket,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        # Apply bucket policy
        policy_str = json.dumps(policy).replace("AMPLIFY_BUCKET", amplifyBucket)
        s3.put_bucket_policy(Bucket=amplifyBucket, Policy=policy_str)
        
        responseData['Data'] = "Success"
        cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData)