"""
CloudFormation Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError
import time

logger = logging.getLogger(__name__)

def clean(region, session, dry_run=True):
    """
    Clean CloudFormation resources in the specified region
    
    Args:
        region (str): AWS region
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    cf_client = session.client('cloudformation', region_name=region)
    
    try:
        logger.info(f"Checking for CloudFormation stacks in {region}...")
        
        # Get all stacks
        paginator = cf_client.get_paginator('list_stacks')
        
        # These are the status filters we want to include
        # Excluding DELETE_COMPLETE since those are already deleted
        stack_status_filters = [
            'CREATE_IN_PROGRESS',
            'CREATE_FAILED',
            'CREATE_COMPLETE',
            'ROLLBACK_IN_PROGRESS',
            'ROLLBACK_FAILED',
            'ROLLBACK_COMPLETE',
            'DELETE_IN_PROGRESS',
            'DELETE_FAILED',
            'UPDATE_IN_PROGRESS',
            'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
            'UPDATE_COMPLETE',
            'UPDATE_ROLLBACK_IN_PROGRESS',
            'UPDATE_ROLLBACK_FAILED',
            'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
            'UPDATE_ROLLBACK_COMPLETE',
            'REVIEW_IN_PROGRESS',
            'IMPORT_IN_PROGRESS',
            'IMPORT_COMPLETE',
            'IMPORT_ROLLBACK_IN_PROGRESS',
            'IMPORT_ROLLBACK_FAILED',
            'IMPORT_ROLLBACK_COMPLETE'
        ]
        
        stack_count = 0
        
        for page in paginator.paginate(StackStatusFilter=stack_status_filters):
            for stack in page['StackSummaries']:
                stack_count += 1
                stack_name = stack['StackName']
                stack_id = stack['StackId']
                stack_status = stack['StackStatus']
                
                logger.info(f"Found CloudFormation stack: {stack_name} (ID: {stack_id}, Status: {stack_status})")
                
                # Skip stacks that are already being deleted
                if stack_status in ['DELETE_IN_PROGRESS']:
                    logger.info(f"Skipping stack {stack_name} as it's already being deleted")
                    continue
                
                # For dry run, just log
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete CloudFormation stack: {stack_name}")
                    continue
                
                # For nested stacks, we should delete the root stack
                # We can check if a stack is nested by looking at the 'RootId' field
                if 'RootId' in stack and stack['RootId'] != stack['StackId']:
                    logger.info(f"Stack {stack_name} is a nested stack, skipping (will be deleted when root stack is deleted)")
                    continue
                
                # For stacks in a failed state, we might need to use RetainResources or force deletion
                try:
                    if stack_status in ['CREATE_FAILED', 'ROLLBACK_FAILED', 'UPDATE_ROLLBACK_FAILED', 'DELETE_FAILED']:
                        # First try to get resources that might be causing deletion failure
                        try:
                            resources = cf_client.list_stack_resources(StackName=stack_name)
                            retain_resources = []
                            for resource in resources.get('StackResourceSummaries', []):
                                if resource.get('ResourceStatus') in ['CREATE_FAILED', 'DELETE_FAILED']:
                                    retain_resources.append(resource['LogicalResourceId'])
                                    logger.warning(f"Resource {resource['LogicalResourceId']} in failed state, will be retained")
                            
                            if retain_resources:
                                logger.warning(f"Deleting failed stack {stack_name} with RetainResources option")
                                cf_client.delete_stack(StackName=stack_name, RetainResources=retain_resources)
                            else:
                                logger.warning(f"Deleting failed stack {stack_name}")
                                cf_client.delete_stack(StackName=stack_name)
                        except ClientError as e:
                            logger.error(f"Error listing resources for failed stack {stack_name}: {str(e)}")
                            logger.warning(f"Attempting to delete failed stack {stack_name} without RetainResources")
                            cf_client.delete_stack(StackName=stack_name)
                    else:
                        logger.warning(f"Deleting CloudFormation stack: {stack_name}")
                        cf_client.delete_stack(StackName=stack_name)
                    
                    logger.warning(f"Successfully initiated deletion for CloudFormation stack {stack_name}")
                except ClientError as e:
                    logger.error(f"Failed to delete CloudFormation stack {stack_name}: {str(e)}")
        
        if stack_count == 0:
            logger.info(f"No CloudFormation stacks found in {region}")
        
    except ClientError as e:
        logger.error(f"Error listing CloudFormation stacks in {region}: {str(e)}")
    
    logger.info(f"Completed CloudFormation stack cleanup in {region}") 