"""
S3 Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def clean(region, session, dry_run=True):
    """
    Clean S3 resources
    Note: S3 is a global service but buckets have a region
    
    Args:
        region (str): AWS region
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    s3_client = session.client('s3', region_name=region)
    s3_resource = session.resource('s3', region_name=region)
    
    try:
        logger.info(f"Checking for S3 buckets in {region}...")
        # List all buckets
        buckets = s3_client.list_buckets()
        
        # Filter buckets by region
        region_buckets = []
        for bucket in buckets['Buckets']:
            bucket_name = bucket['Name']
            try:
                # Get bucket location/region
                bucket_region = s3_client.get_bucket_location(Bucket=bucket_name)
                bucket_region = bucket_region['LocationConstraint'] or 'us-east-1'  # None maps to us-east-1
                
                if bucket_region == region:
                    region_buckets.append(bucket_name)
                    logger.info(f"Found S3 bucket in {region}: {bucket_name}")
            except ClientError as e:
                logger.error(f"Error getting location for bucket {bucket_name}: {str(e)}")
        
        if not region_buckets:
            logger.info(f"No S3 buckets found in {region}")
            return
        
        # Empty and delete each bucket in the region
        for bucket_name in region_buckets:
            logger.info(f"Processing bucket: {bucket_name}")
            
            # Check if versioning is enabled
            try:
                versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
                is_versioned = versioning.get('Status') == 'Enabled' or versioning.get('Status') == 'Suspended'
                logger.info(f"Bucket {bucket_name} versioning status: {versioning.get('Status', 'Not enabled')}")
            except ClientError as e:
                logger.error(f"Error checking versioning for bucket {bucket_name}: {str(e)}")
                is_versioned = False
            
            # Delete all objects (including versions if versioning is enabled)
            if not dry_run:
                try:
                    bucket = s3_resource.Bucket(bucket_name)
                    
                    # Check for object lock
                    try:
                        object_lock = s3_client.get_object_lock_configuration(Bucket=bucket_name)
                        if 'ObjectLockConfiguration' in object_lock:
                            logger.warning(f"Bucket {bucket_name} has Object Lock enabled. Some objects may not be deletable.")
                    except ClientError as e:
                        # If object lock isn't configured, this call will fail
                        if 'ObjectLockConfigurationNotFoundError' not in str(e):
                            logger.error(f"Error checking object lock for bucket {bucket_name}: {str(e)}")
                    
                    if is_versioned:
                        logger.warning(f"Deleting all objects and versions from bucket {bucket_name}")
                        bucket.object_versions.delete()
                    else:
                        logger.warning(f"Deleting all objects from bucket {bucket_name}")
                        bucket.objects.all().delete()
                    
                    # Delete bucket lifecycle configuration
                    try:
                        s3_client.delete_bucket_lifecycle(Bucket=bucket_name)
                        logger.info(f"Deleted lifecycle configuration for bucket {bucket_name}")
                    except ClientError as e:
                        # Ignore if lifecycle configuration doesn't exist
                        if 'NoSuchLifecycleConfiguration' not in str(e):
                            logger.error(f"Error deleting lifecycle configuration for bucket {bucket_name}: {str(e)}")
                    
                    # Delete bucket policy
                    try:
                        s3_client.delete_bucket_policy(Bucket=bucket_name)
                        logger.info(f"Deleted bucket policy for bucket {bucket_name}")
                    except ClientError as e:
                        # Ignore if policy doesn't exist
                        if 'NoSuchBucketPolicy' not in str(e):
                            logger.error(f"Error deleting bucket policy for bucket {bucket_name}: {str(e)}")
                    
                    # Delete bucket
                    logger.warning(f"Deleting bucket: {bucket_name}")
                    s3_client.delete_bucket(Bucket=bucket_name)
                    logger.warning(f"Successfully deleted bucket {bucket_name}")
                    
                except ClientError as e:
                    if 'BucketNotEmpty' in str(e):
                        logger.error(f"Bucket {bucket_name} could not be deleted because it's not empty")
                    else:
                        logger.error(f"Failed to delete bucket {bucket_name}: {str(e)}")
            else:
                logger.info(f"[DRY RUN] Would delete bucket: {bucket_name} and all its contents")
                
    except ClientError as e:
        logger.error(f"Error listing S3 buckets in {region}: {str(e)}")
        
    logger.info(f"Completed S3 resource cleanup in {region}") 