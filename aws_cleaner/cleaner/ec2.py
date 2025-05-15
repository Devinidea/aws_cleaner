"""
EC2 Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def clean(region, session, dry_run=True):
    """
    Clean EC2 resources in the specified region
    
    Args:
        region (str): AWS region
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    ec2_client = session.client('ec2', region_name=region)
    ec2_resource = session.resource('ec2', region_name=region)
    
    # Clean in the following order:
    # 1. Instances
    # 2. Security Groups (after instances)
    # 3. Elastic IPs
    # 4. Volumes
    # 5. Snapshots
    # 6. AMIs
    
    # 1. Terminate EC2 instances
    try:
        logger.info(f"Checking for EC2 instances in {region}...")
        instances = ec2_resource.instances.all()
        instance_count = 0
        
        for instance in instances:
            instance_count += 1
            if instance.state['Name'] in ['terminated', 'shutting-down']:
                logger.info(f"Skipping instance {instance.id} as it's already {instance.state['Name']}")
                continue
                
            instance_name = "N/A"
            if instance.tags:
                for tag in instance.tags:
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break
            
            logger.info(f"Found EC2 instance: {instance.id} (Name: {instance_name}, State: {instance.state['Name']})")
            
            if not dry_run:
                try:
                    logger.warning(f"Terminating EC2 instance: {instance.id}")
                    instance.terminate()
                    logger.warning(f"Successfully initiated termination for instance {instance.id}")
                except ClientError as e:
                    logger.error(f"Failed to terminate EC2 instance {instance.id}: {str(e)}")
        
        if instance_count == 0:
            logger.info(f"No EC2 instances found in {region}")
    except ClientError as e:
        logger.error(f"Error listing EC2 instances in {region}: {str(e)}")
    
    # 2. Delete security groups (after instances are terminated)
    try:
        logger.info(f"Checking for EC2 security groups in {region}...")
        security_groups = ec2_client.describe_security_groups()
        
        # Skip default security groups
        non_default_sgs = [sg for sg in security_groups['SecurityGroups'] 
                          if sg['GroupName'] != 'default']
        
        if not non_default_sgs:
            logger.info(f"No non-default security groups found in {region}")
        
        for sg in non_default_sgs:
            logger.info(f"Found security group: {sg['GroupId']} (Name: {sg['GroupName']})")
            
            if not dry_run:
                try:
                    logger.warning(f"Deleting security group: {sg['GroupId']}")
                    ec2_client.delete_security_group(GroupId=sg['GroupId'])
                    logger.warning(f"Successfully deleted security group {sg['GroupId']}")
                except ClientError as e:
                    # This is expected if SG is still in use by instances or other SGs
                    if "has a dependent object" in str(e) or "currently in use by" in str(e):
                        logger.warning(f"Security group {sg['GroupId']} is still in use, cannot delete now")
                    else:
                        logger.error(f"Failed to delete security group {sg['GroupId']}: {str(e)}")
    except ClientError as e:
        logger.error(f"Error listing security groups in {region}: {str(e)}")
    
    # 3. Release Elastic IPs
    try:
        logger.info(f"Checking for Elastic IPs in {region}...")
        addresses = ec2_client.describe_addresses()
        
        if not addresses['Addresses']:
            logger.info(f"No Elastic IPs found in {region}")
        
        for eip in addresses['Addresses']:
            allocation_id = eip.get('AllocationId')
            public_ip = eip.get('PublicIp', 'N/A')
            
            if not allocation_id:
                logger.info(f"Skipping Elastic IP {public_ip} (no AllocationId)")
                continue
                
            logger.info(f"Found Elastic IP: {allocation_id} (Public IP: {public_ip})")
            
            if not dry_run:
                try:
                    logger.warning(f"Releasing Elastic IP: {allocation_id}")
                    ec2_client.release_address(AllocationId=allocation_id)
                    logger.warning(f"Successfully released Elastic IP {allocation_id}")
                except ClientError as e:
                    logger.error(f"Failed to release Elastic IP {allocation_id}: {str(e)}")
    except ClientError as e:
        logger.error(f"Error listing Elastic IPs in {region}: {str(e)}")
    
    # 4. Delete EBS volumes
    try:
        logger.info(f"Checking for EBS volumes in {region}...")
        volumes = ec2_resource.volumes.all()
        volume_count = 0
        
        for volume in volumes:
            volume_count += 1
            volume_name = "N/A"
            if volume.tags:
                for tag in volume.tags:
                    if tag['Key'] == 'Name':
                        volume_name = tag['Value']
                        break
                        
            logger.info(f"Found EBS volume: {volume.id} (Name: {volume_name}, State: {volume.state})")
            
            if volume.state == 'in-use':
                logger.warning(f"Volume {volume.id} is still in use, cannot delete now")
                continue
                
            if not dry_run:
                try:
                    logger.warning(f"Deleting EBS volume: {volume.id}")
                    volume.delete()
                    logger.warning(f"Successfully deleted EBS volume {volume.id}")
                except ClientError as e:
                    logger.error(f"Failed to delete EBS volume {volume.id}: {str(e)}")
        
        if volume_count == 0:
            logger.info(f"No EBS volumes found in {region}")
    except ClientError as e:
        logger.error(f"Error listing EBS volumes in {region}: {str(e)}")
    
    # 5. Delete snapshots owned by this account
    try:
        logger.info(f"Checking for EBS snapshots in {region}...")
        account_id = session.client('sts').get_caller_identity().get('Account')
        snapshots = ec2_client.describe_snapshots(OwnerIds=[account_id])
        
        if not snapshots['Snapshots']:
            logger.info(f"No EBS snapshots found in {region}")
        
        for snapshot in snapshots['Snapshots']:
            logger.info(f"Found EBS snapshot: {snapshot['SnapshotId']} (Description: {snapshot.get('Description', 'N/A')})")
            
            if not dry_run:
                try:
                    logger.warning(f"Deleting EBS snapshot: {snapshot['SnapshotId']}")
                    ec2_client.delete_snapshot(SnapshotId=snapshot['SnapshotId'])
                    logger.warning(f"Successfully deleted EBS snapshot {snapshot['SnapshotId']}")
                except ClientError as e:
                    logger.error(f"Failed to delete EBS snapshot {snapshot['SnapshotId']}: {str(e)}")
    except ClientError as e:
        logger.error(f"Error listing EBS snapshots in {region}: {str(e)}")
    
    # 6. Deregister AMIs and delete associated snapshots
    try:
        logger.info(f"Checking for AMIs in {region}...")
        account_id = session.client('sts').get_caller_identity().get('Account')
        images = ec2_client.describe_images(Owners=[account_id])
        
        if not images['Images']:
            logger.info(f"No AMIs found in {region}")
        
        for image in images['Images']:
            logger.info(f"Found AMI: {image['ImageId']} (Name: {image.get('Name', 'N/A')})")
            
            if not dry_run:
                try:
                    logger.warning(f"Deregistering AMI: {image['ImageId']}")
                    ec2_client.deregister_image(ImageId=image['ImageId'])
                    logger.warning(f"Successfully deregistered AMI {image['ImageId']}")
                    
                    # Delete associated snapshots
                    for bdm in image.get('BlockDeviceMappings', []):
                        if 'Ebs' in bdm and 'SnapshotId' in bdm['Ebs']:
                            snapshot_id = bdm['Ebs']['SnapshotId']
                            try:
                                logger.warning(f"Deleting snapshot associated with AMI: {snapshot_id}")
                                ec2_client.delete_snapshot(SnapshotId=snapshot_id)
                                logger.warning(f"Successfully deleted snapshot {snapshot_id}")
                            except ClientError as e:
                                logger.error(f"Failed to delete snapshot {snapshot_id}: {str(e)}")
                except ClientError as e:
                    logger.error(f"Failed to deregister AMI {image['ImageId']}: {str(e)}")
    except ClientError as e:
        logger.error(f"Error listing AMIs in {region}: {str(e)}")
        
    logger.info(f"Completed EC2 resource cleanup in {region}") 