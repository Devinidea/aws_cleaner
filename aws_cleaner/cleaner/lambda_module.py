"""
Lambda Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def clean(region, session, dry_run=True):
    """
    Clean Lambda resources in the specified region
    
    Args:
        region (str): AWS region
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    lambda_client = session.client('lambda', region_name=region)
    
    try:
        logger.info(f"Checking for Lambda functions in {region}...")
        
        # Get all Lambda functions
        paginator = lambda_client.get_paginator('list_functions')
        function_count = 0
        
        for page in paginator.paginate():
            for function in page['Functions']:
                function_count += 1
                function_name = function['FunctionName']
                function_arn = function['FunctionArn']
                runtime = function.get('Runtime', 'N/A')
                
                logger.info(f"Found Lambda function: {function_name} (ARN: {function_arn}, Runtime: {runtime})")
                
                if not dry_run:
                    # First remove event source mappings
                    try:
                        mappings = lambda_client.list_event_source_mappings(FunctionName=function_name)
                        for mapping in mappings.get('EventSourceMappings', []):
                            mapping_uuid = mapping['UUID']
                            logger.warning(f"Deleting event source mapping {mapping_uuid} for function {function_name}")
                            lambda_client.delete_event_source_mapping(UUID=mapping_uuid)
                            logger.warning(f"Successfully deleted event source mapping {mapping_uuid}")
                    except ClientError as e:
                        logger.error(f"Error deleting event source mappings for function {function_name}: {str(e)}")
                    
                    # Delete function and all its versions and aliases
                    try:
                        logger.warning(f"Deleting Lambda function: {function_name}")
                        lambda_client.delete_function(FunctionName=function_name)
                        logger.warning(f"Successfully deleted Lambda function {function_name}")
                    except ClientError as e:
                        logger.error(f"Failed to delete Lambda function {function_name}: {str(e)}")
        
        if function_count == 0:
            logger.info(f"No Lambda functions found in {region}")
            
        # Clean Lambda layers
        logger.info(f"Checking for Lambda layers in {region}...")
        
        layers_paginator = lambda_client.get_paginator('list_layers')
        layer_count = 0
        
        for page in layers_paginator.paginate():
            for layer in page.get('Layers', []):
                layer_count += 1
                layer_name = layer['LayerName']
                layer_arn = layer.get('LayerArn')
                
                logger.info(f"Found Lambda layer: {layer_name} (ARN: {layer_arn})")
                
                if not dry_run:
                    try:
                        # Get all versions of this layer
                        versions_paginator = lambda_client.get_paginator('list_layer_versions')
                        for v_page in versions_paginator.paginate(LayerName=layer_name):
                            for version in v_page.get('LayerVersions', []):
                                version_number = version.get('Version')
                                version_arn = version.get('LayerVersionArn')
                                
                                logger.warning(f"Deleting Lambda layer version: {layer_name}:{version_number} (ARN: {version_arn})")
                                lambda_client.delete_layer_version(
                                    LayerName=layer_name,
                                    VersionNumber=version_number
                                )
                                logger.warning(f"Successfully deleted Lambda layer version {layer_name}:{version_number}")
                    except ClientError as e:
                        logger.error(f"Failed to delete Lambda layer {layer_name}: {str(e)}")
        
        if layer_count == 0:
            logger.info(f"No Lambda layers found in {region}")
            
    except ClientError as e:
        logger.error(f"Error listing Lambda resources in {region}: {str(e)}")
        
    logger.info(f"Completed Lambda resource cleanup in {region}") 