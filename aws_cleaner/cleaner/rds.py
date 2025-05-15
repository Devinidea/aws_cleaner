"""
RDS Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError
import time

logger = logging.getLogger(__name__)

def clean(region, session, dry_run=True):
    """
    Clean RDS resources in the specified region
    
    Args:
        region (str): AWS region
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    rds_client = session.client('rds', region_name=region)
    
    try:
        # Clean in the following order:
        # 1. DB instances
        # 2. DB clusters (Aurora)
        # 3. DB snapshots
        # 4. DB cluster snapshots
        # 5. DB parameter groups
        # 6. DB cluster parameter groups
        # 7. DB subnet groups
        # 8. DB option groups
        # 9. DB event subscriptions
        
        # 1. Delete DB instances
        logger.info(f"Checking for RDS DB instances in {region}...")
        try:
            paginator = rds_client.get_paginator('describe_db_instances')
            instance_count = 0
            
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    instance_count += 1
                    instance_id = instance['DBInstanceIdentifier']
                    engine = instance.get('Engine', 'N/A')
                    status = instance.get('DBInstanceStatus', 'N/A')
                    
                    logger.info(f"Found RDS instance: {instance_id} (Engine: {engine}, Status: {status})")
                    
                    if not dry_run:
                        try:
                            # Check if instance is part of a cluster
                            if 'DBClusterIdentifier' in instance:
                                logger.info(f"Instance {instance_id} is part of cluster {instance['DBClusterIdentifier']}, skipping (will be deleted with cluster)")
                                continue
                                
                            # Skip deletion protection check in dry run mode
                            if instance.get('DeletionProtection', False):
                                logger.warning(f"RDS instance {instance_id} has deletion protection enabled, disabling...")
                                rds_client.modify_db_instance(
                                    DBInstanceIdentifier=instance_id,
                                    DeletionProtection=False,
                                    ApplyImmediately=True
                                )
                                # Wait for modification to apply
                                logger.info(f"Waiting for deletion protection modification to apply for {instance_id}...")
                                time.sleep(10)
                            
                            # Delete the instance without final snapshot
                            logger.warning(f"Deleting RDS instance: {instance_id}")
                            rds_client.delete_db_instance(
                                DBInstanceIdentifier=instance_id,
                                SkipFinalSnapshot=True,
                                DeleteAutomatedBackups=True
                            )
                            logger.warning(f"Successfully initiated deletion for RDS instance {instance_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete RDS instance {instance_id}: {str(e)}")
            
            if instance_count == 0:
                logger.info(f"No RDS DB instances found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS instances in {region}: {str(e)}")
        
        # 2. Delete Aurora DB clusters
        logger.info(f"Checking for RDS DB clusters in {region}...")
        try:
            cluster_paginator = rds_client.get_paginator('describe_db_clusters')
            cluster_count = 0
            
            for page in cluster_paginator.paginate():
                for cluster in page['DBClusters']:
                    cluster_count += 1
                    cluster_id = cluster['DBClusterIdentifier']
                    engine = cluster.get('Engine', 'N/A')
                    status = cluster.get('Status', 'N/A')
                    
                    logger.info(f"Found RDS cluster: {cluster_id} (Engine: {engine}, Status: {status})")
                    
                    if not dry_run:
                        try:
                            # Disable deletion protection if enabled
                            if cluster.get('DeletionProtection', False):
                                logger.warning(f"RDS cluster {cluster_id} has deletion protection enabled, disabling...")
                                rds_client.modify_db_cluster(
                                    DBClusterIdentifier=cluster_id,
                                    DeletionProtection=False,
                                    ApplyImmediately=True
                                )
                                # Wait for modification to apply
                                logger.info(f"Waiting for deletion protection modification to apply for cluster {cluster_id}...")
                                time.sleep(10)
                            
                            # Delete the cluster without final snapshot
                            logger.warning(f"Deleting RDS cluster: {cluster_id}")
                            rds_client.delete_db_cluster(
                                DBClusterIdentifier=cluster_id,
                                SkipFinalSnapshot=True
                            )
                            logger.warning(f"Successfully initiated deletion for RDS cluster {cluster_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete RDS cluster {cluster_id}: {str(e)}")
            
            if cluster_count == 0:
                logger.info(f"No RDS DB clusters found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS clusters in {region}: {str(e)}")
        
        # 3. Delete DB snapshots
        logger.info(f"Checking for RDS DB snapshots in {region}...")
        try:
            snapshot_paginator = rds_client.get_paginator('describe_db_snapshots')
            snapshot_count = 0
            
            for page in snapshot_paginator.paginate():
                for snapshot in page['DBSnapshots']:
                    snapshot_count += 1
                    snapshot_id = snapshot['DBSnapshotIdentifier']
                    instance_id = snapshot.get('DBInstanceIdentifier', 'N/A')
                    status = snapshot.get('Status', 'N/A')
                    
                    logger.info(f"Found RDS snapshot: {snapshot_id} (Instance: {instance_id}, Status: {status})")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting RDS snapshot: {snapshot_id}")
                            rds_client.delete_db_snapshot(DBSnapshotIdentifier=snapshot_id)
                            logger.warning(f"Successfully deleted RDS snapshot {snapshot_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete RDS snapshot {snapshot_id}: {str(e)}")
            
            if snapshot_count == 0:
                logger.info(f"No RDS DB snapshots found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS snapshots in {region}: {str(e)}")
        
        # 4. Delete DB cluster snapshots
        logger.info(f"Checking for RDS DB cluster snapshots in {region}...")
        try:
            cluster_snapshot_paginator = rds_client.get_paginator('describe_db_cluster_snapshots')
            cluster_snapshot_count = 0
            
            for page in cluster_snapshot_paginator.paginate():
                for snapshot in page['DBClusterSnapshots']:
                    cluster_snapshot_count += 1
                    snapshot_id = snapshot['DBClusterSnapshotIdentifier']
                    cluster_id = snapshot.get('DBClusterIdentifier', 'N/A')
                    status = snapshot.get('Status', 'N/A')
                    
                    logger.info(f"Found RDS cluster snapshot: {snapshot_id} (Cluster: {cluster_id}, Status: {status})")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting RDS cluster snapshot: {snapshot_id}")
                            rds_client.delete_db_cluster_snapshot(DBClusterSnapshotIdentifier=snapshot_id)
                            logger.warning(f"Successfully deleted RDS cluster snapshot {snapshot_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete RDS cluster snapshot {snapshot_id}: {str(e)}")
            
            if cluster_snapshot_count == 0:
                logger.info(f"No RDS DB cluster snapshots found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS cluster snapshots in {region}: {str(e)}")
        
        # 5. Delete DB parameter groups (custom only)
        logger.info(f"Checking for custom RDS parameter groups in {region}...")
        try:
            param_paginator = rds_client.get_paginator('describe_db_parameter_groups')
            param_group_count = 0
            
            for page in param_paginator.paginate():
                for param_group in page['DBParameterGroups']:
                    # Skip default parameter groups which cannot be deleted
                    if param_group['DBParameterGroupName'].startswith('default.'):
                        continue
                        
                    param_group_count += 1
                    param_group_name = param_group['DBParameterGroupName']
                    
                    logger.info(f"Found custom RDS parameter group: {param_group_name}")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting RDS parameter group: {param_group_name}")
                            rds_client.delete_db_parameter_group(DBParameterGroupName=param_group_name)
                            logger.warning(f"Successfully deleted RDS parameter group {param_group_name}")
                        except ClientError as e:
                            # This is expected if the parameter group is still in use
                            if "is currently in use" in str(e):
                                logger.warning(f"Parameter group {param_group_name} is still in use, cannot delete now")
                            else:
                                logger.error(f"Failed to delete RDS parameter group {param_group_name}: {str(e)}")
            
            if param_group_count == 0:
                logger.info(f"No custom RDS parameter groups found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS parameter groups in {region}: {str(e)}")
        
        # 6. Delete DB cluster parameter groups (custom only)
        logger.info(f"Checking for custom RDS cluster parameter groups in {region}...")
        try:
            cluster_param_paginator = rds_client.get_paginator('describe_db_cluster_parameter_groups')
            cluster_param_group_count = 0
            
            for page in cluster_param_paginator.paginate():
                for param_group in page['DBClusterParameterGroups']:
                    # Skip default parameter groups which cannot be deleted
                    if param_group['DBClusterParameterGroupName'].startswith('default.'):
                        continue
                        
                    cluster_param_group_count += 1
                    param_group_name = param_group['DBClusterParameterGroupName']
                    
                    logger.info(f"Found custom RDS cluster parameter group: {param_group_name}")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting RDS cluster parameter group: {param_group_name}")
                            rds_client.delete_db_cluster_parameter_group(DBClusterParameterGroupName=param_group_name)
                            logger.warning(f"Successfully deleted RDS cluster parameter group {param_group_name}")
                        except ClientError as e:
                            # This is expected if the parameter group is still in use
                            if "is currently in use" in str(e):
                                logger.warning(f"Cluster parameter group {param_group_name} is still in use, cannot delete now")
                            else:
                                logger.error(f"Failed to delete RDS cluster parameter group {param_group_name}: {str(e)}")
            
            if cluster_param_group_count == 0:
                logger.info(f"No custom RDS cluster parameter groups found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS cluster parameter groups in {region}: {str(e)}")
        
        # 7. Delete DB subnet groups
        logger.info(f"Checking for RDS subnet groups in {region}...")
        try:
            subnet_paginator = rds_client.get_paginator('describe_db_subnet_groups')
            subnet_group_count = 0
            
            for page in subnet_paginator.paginate():
                for subnet_group in page['DBSubnetGroups']:
                    subnet_group_count += 1
                    subnet_group_name = subnet_group['DBSubnetGroupName']
                    
                    logger.info(f"Found RDS subnet group: {subnet_group_name}")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting RDS subnet group: {subnet_group_name}")
                            rds_client.delete_db_subnet_group(DBSubnetGroupName=subnet_group_name)
                            logger.warning(f"Successfully deleted RDS subnet group {subnet_group_name}")
                        except ClientError as e:
                            # This is expected if the subnet group is still in use
                            if "is currently in use" in str(e):
                                logger.warning(f"Subnet group {subnet_group_name} is still in use, cannot delete now")
                            else:
                                logger.error(f"Failed to delete RDS subnet group {subnet_group_name}: {str(e)}")
            
            if subnet_group_count == 0:
                logger.info(f"No RDS subnet groups found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS subnet groups in {region}: {str(e)}")
        
        # 8. Delete DB option groups (custom only)
        logger.info(f"Checking for custom RDS option groups in {region}...")
        try:
            option_paginator = rds_client.get_paginator('describe_option_groups')
            option_group_count = 0
            
            for page in option_paginator.paginate():
                for option_group in page['OptionGroupsList']:
                    # Skip default option groups which cannot be deleted
                    if option_group['OptionGroupName'].startswith('default:'):
                        continue
                        
                    option_group_count += 1
                    option_group_name = option_group['OptionGroupName']
                    
                    logger.info(f"Found custom RDS option group: {option_group_name}")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting RDS option group: {option_group_name}")
                            rds_client.delete_option_group(OptionGroupName=option_group_name)
                            logger.warning(f"Successfully deleted RDS option group {option_group_name}")
                        except ClientError as e:
                            # This is expected if the option group is still in use
                            if "is currently in use" in str(e):
                                logger.warning(f"Option group {option_group_name} is still in use, cannot delete now")
                            else:
                                logger.error(f"Failed to delete RDS option group {option_group_name}: {str(e)}")
            
            if option_group_count == 0:
                logger.info(f"No custom RDS option groups found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS option groups in {region}: {str(e)}")
        
        # 9. Delete DB event subscriptions
        logger.info(f"Checking for RDS event subscriptions in {region}...")
        try:
            event_subscriptions = rds_client.describe_event_subscriptions()
            subscription_count = 0
            
            for subscription in event_subscriptions.get('EventSubscriptionsList', []):
                subscription_count += 1
                subscription_name = subscription['CustSubscriptionId']
                
                logger.info(f"Found RDS event subscription: {subscription_name}")
                
                if not dry_run:
                    try:
                        logger.warning(f"Deleting RDS event subscription: {subscription_name}")
                        rds_client.delete_event_subscription(SubscriptionName=subscription_name)
                        logger.warning(f"Successfully deleted RDS event subscription {subscription_name}")
                    except ClientError as e:
                        logger.error(f"Failed to delete RDS event subscription {subscription_name}: {str(e)}")
            
            if subscription_count == 0:
                logger.info(f"No RDS event subscriptions found in {region}")
        except ClientError as e:
            logger.error(f"Error listing RDS event subscriptions in {region}: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error cleaning RDS resources in {region}: {str(e)}")
        
    logger.info(f"Completed RDS resource cleanup in {region}") 