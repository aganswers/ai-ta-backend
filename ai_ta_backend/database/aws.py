import os

import boto3
from boto3.session import Config as BotoConfig
from injector import inject


class AWSStorage:

  @inject
  def __init__(self):
    endpoint = (os.environ.get('CLOUDFLARE_R2_ENDPOINT') or
                os.environ.get('MINIO_API_URL'))

    access_key = (os.environ.get('AGANSWERS_AWS_ACCESS_KEY_ID') or
                  os.environ.get('AWS_ACCESS_KEY_ID') or
                  os.environ.get('AWS_KEY'))

    secret_key = (os.environ.get('AGANSWERS_AWS_SECRET_ACCESS_KEY') or
                  os.environ.get('AWS_SECRET_ACCESS_KEY') or
                  os.environ.get('AWS_SECRET'))

    if not access_key or not secret_key:
      raise ValueError('Missing S3 credentials: expected AGANSWERS_AWS_ACCESS_KEY_ID/AWS_KEY and secret')

    client_config = BotoConfig(s3={'addressing_style': 'path'})

    self.s3_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get('AWS_REGION', 'auto'),
        config=client_config,
    )

  def upload_file(self, file_path: str, bucket_name: str, object_name: str):
    self.s3_client.upload_file(file_path, bucket_name, object_name)

  def download_file(self, object_name: str, bucket_name: str, file_path: str):
    self.s3_client.download_file(bucket_name, object_name, file_path)

  def delete_file(self, bucket_name: str, s3_path: str):
    return self.s3_client.delete_object(Bucket=bucket_name, Key=s3_path)

  def generatePresignedUrl(self, object: str, bucket_name: str, s3_path: str, expiration: int = 3600):
    # generate presigned URL
    return self.s3_client.generate_presigned_url('get_object',
                                                 Params={
                                                     'Bucket': bucket_name,
                                                     'Key': s3_path
                                                 },
                                                 ExpiresIn=expiration)
