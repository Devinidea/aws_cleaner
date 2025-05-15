"""
IAM Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError
import time

logger = logging.getLogger(__name__)

def clean(session, dry_run=True):
    """
    Clean IAM resources (IAM is a global service, no region needed)
    
    Args:
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    iam_client = session.client('iam')
    
    try:
        # Clean IAM resources in the following order:
        # 1. IAM Access Keys (user's)
        # 2. IAM User Policies
        # 3. IAM Group Memberships
        # 4. IAM Users
        # 5. IAM Group Policies
        # 6. IAM Groups
        # 7. IAM Role Policies
        # 8. IAM Roles
        # 9. IAM Policy Versions
        # 10. IAM Policies (customer managed)
        # Note: We can't delete AWS-managed policies
        
        # Get account alias for logging
        try:
            account_aliases = iam_client.list_account_aliases()
            account_alias = account_aliases['AccountAliases'][0] if account_aliases['AccountAliases'] else "No alias"
            logger.info(f"Processing IAM resources for account: {account_alias}")
        except ClientError as e:
            logger.error(f"Error getting account alias: {str(e)}")
            account_alias = "Unknown"
        
        # 1 & 2 & 3 & 4. Process IAM Users, including their Access Keys and Policies
        logger.info("Checking for IAM Users...")
        try:
            paginator = iam_client.get_paginator('list_users')
            user_count = 0
            
            for page in paginator.paginate():
                for user in page['Users']:
                    user_count += 1
                    user_name = user['UserName']
                    
                    logger.info(f"Found IAM User: {user_name}")
                    
                    if not dry_run:
                        # 1. Delete access keys
                        try:
                            access_keys = iam_client.list_access_keys(UserName=user_name)
                            for key in access_keys.get('AccessKeyMetadata', []):
                                key_id = key['AccessKeyId']
                                logger.warning(f"Deleting access key {key_id} for user {user_name}")
                                iam_client.delete_access_key(UserName=user_name, AccessKeyId=key_id)
                                logger.warning(f"Successfully deleted access key {key_id}")
                        except ClientError as e:
                            logger.error(f"Error deleting access keys for user {user_name}: {str(e)}")
                        
                        # 2. Delete inline policies
                        try:
                            policy_names = iam_client.list_user_policies(UserName=user_name)
                            for policy_name in policy_names.get('PolicyNames', []):
                                logger.warning(f"Deleting inline policy {policy_name} from user {user_name}")
                                iam_client.delete_user_policy(UserName=user_name, PolicyName=policy_name)
                                logger.warning(f"Successfully deleted inline policy {policy_name} from user {user_name}")
                        except ClientError as e:
                            logger.error(f"Error deleting inline policies for user {user_name}: {str(e)}")
                        
                        # Detach managed policies
                        try:
                            attached_policies = iam_client.list_attached_user_policies(UserName=user_name)
                            for policy in attached_policies.get('AttachedPolicies', []):
                                policy_arn = policy['PolicyArn']
                                logger.warning(f"Detaching managed policy {policy_arn} from user {user_name}")
                                iam_client.detach_user_policy(UserName=user_name, PolicyArn=policy_arn)
                                logger.warning(f"Successfully detached managed policy {policy_arn} from user {user_name}")
                        except ClientError as e:
                            logger.error(f"Error detaching managed policies from user {user_name}: {str(e)}")
                        
                        # 3. Remove from groups
                        try:
                            groups = iam_client.list_groups_for_user(UserName=user_name)
                            for group in groups.get('Groups', []):
                                group_name = group['GroupName']
                                logger.warning(f"Removing user {user_name} from group {group_name}")
                                iam_client.remove_user_from_group(UserName=user_name, GroupName=group_name)
                                logger.warning(f"Successfully removed user {user_name} from group {group_name}")
                        except ClientError as e:
                            logger.error(f"Error removing user {user_name} from groups: {str(e)}")
                        
                        # Delete MFA devices
                        try:
                            mfa_devices = iam_client.list_mfa_devices(UserName=user_name)
                            for device in mfa_devices.get('MFADevices', []):
                                device_serial = device['SerialNumber']
                                logger.warning(f"Deactivating MFA device {device_serial} for user {user_name}")
                                iam_client.deactivate_mfa_device(UserName=user_name, SerialNumber=device_serial)
                                logger.warning(f"Successfully deactivated MFA device {device_serial}")
                        except ClientError as e:
                            logger.error(f"Error deactivating MFA devices for user {user_name}: {str(e)}")
                        
                        # Delete login profile if exists
                        try:
                            iam_client.get_login_profile(UserName=user_name)
                            logger.warning(f"Deleting login profile for user {user_name}")
                            iam_client.delete_login_profile(UserName=user_name)
                            logger.warning(f"Successfully deleted login profile for user {user_name}")
                        except ClientError as e:
                            # It's OK if the user doesn't have a login profile
                            if 'NoSuchEntity' not in str(e):
                                logger.error(f"Error deleting login profile for user {user_name}: {str(e)}")
                        
                        # 4. Delete the user
                        try:
                            logger.warning(f"Deleting IAM User: {user_name}")
                            iam_client.delete_user(UserName=user_name)
                            logger.warning(f"Successfully deleted IAM User {user_name}")
                        except ClientError as e:
                            logger.error(f"Failed to delete IAM User {user_name}: {str(e)}")
            
            if user_count == 0:
                logger.info("No IAM Users found")
        except ClientError as e:
            logger.error(f"Error listing IAM Users: {str(e)}")
        
        # 5 & 6. Process IAM Groups and their Policies
        logger.info("Checking for IAM Groups...")
        try:
            group_paginator = iam_client.get_paginator('list_groups')
            group_count = 0
            
            for page in group_paginator.paginate():
                for group in page['Groups']:
                    group_count += 1
                    group_name = group['GroupName']
                    
                    logger.info(f"Found IAM Group: {group_name}")
                    
                    if not dry_run:
                        # 5. Delete inline policies
                        try:
                            policy_names = iam_client.list_group_policies(GroupName=group_name)
                            for policy_name in policy_names.get('PolicyNames', []):
                                logger.warning(f"Deleting inline policy {policy_name} from group {group_name}")
                                iam_client.delete_group_policy(GroupName=group_name, PolicyName=policy_name)
                                logger.warning(f"Successfully deleted inline policy {policy_name} from group {group_name}")
                        except ClientError as e:
                            logger.error(f"Error deleting inline policies for group {group_name}: {str(e)}")
                        
                        # Detach managed policies
                        try:
                            attached_policies = iam_client.list_attached_group_policies(GroupName=group_name)
                            for policy in attached_policies.get('AttachedPolicies', []):
                                policy_arn = policy['PolicyArn']
                                logger.warning(f"Detaching managed policy {policy_arn} from group {group_name}")
                                iam_client.detach_group_policy(GroupName=group_name, PolicyArn=policy_arn)
                                logger.warning(f"Successfully detached managed policy {policy_arn} from group {group_name}")
                        except ClientError as e:
                            logger.error(f"Error detaching managed policies from group {group_name}: {str(e)}")
                        
                        # 6. Delete the group
                        try:
                            logger.warning(f"Deleting IAM Group: {group_name}")
                            iam_client.delete_group(GroupName=group_name)
                            logger.warning(f"Successfully deleted IAM Group {group_name}")
                        except ClientError as e:
                            logger.error(f"Failed to delete IAM Group {group_name}: {str(e)}")
            
            if group_count == 0:
                logger.info("No IAM Groups found")
        except ClientError as e:
            logger.error(f"Error listing IAM Groups: {str(e)}")
        
        # 7 & 8. Process IAM Roles and their Policies
        logger.info("Checking for IAM Roles...")
        try:
            role_paginator = iam_client.get_paginator('list_roles')
            role_count = 0
            
            for page in role_paginator.paginate():
                for role in page['Roles']:
                    role_name = role['RoleName']
                    
                    # Skip AWS service-linked roles which can't be manually deleted
                    path = role.get('Path', '')
                    if path.startswith('/aws-service-role/') or path.startswith('/service-role/'):
                        logger.info(f"Skipping service-linked role: {role_name}")
                        continue
                    
                    role_count += 1
                    logger.info(f"Found IAM Role: {role_name}")
                    
                    if not dry_run:
                        # 7. Delete inline policies
                        try:
                            policy_names = iam_client.list_role_policies(RoleName=role_name)
                            for policy_name in policy_names.get('PolicyNames', []):
                                logger.warning(f"Deleting inline policy {policy_name} from role {role_name}")
                                iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                                logger.warning(f"Successfully deleted inline policy {policy_name} from role {role_name}")
                        except ClientError as e:
                            logger.error(f"Error deleting inline policies for role {role_name}: {str(e)}")
                        
                        # Detach managed policies
                        try:
                            attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
                            for policy in attached_policies.get('AttachedPolicies', []):
                                policy_arn = policy['PolicyArn']
                                logger.warning(f"Detaching managed policy {policy_arn} from role {role_name}")
                                iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
                                logger.warning(f"Successfully detached managed policy {policy_arn} from role {role_name}")
                        except ClientError as e:
                            logger.error(f"Error detaching managed policies from role {role_name}: {str(e)}")
                        
                        # 8. Delete the role
                        try:
                            # Delete instance profile associations first
                            try:
                                instance_profiles = iam_client.list_instance_profiles_for_role(RoleName=role_name)
                                for profile in instance_profiles.get('InstanceProfiles', []):
                                    profile_name = profile['InstanceProfileName']
                                    logger.warning(f"Removing role {role_name} from instance profile {profile_name}")
                                    iam_client.remove_role_from_instance_profile(
                                        InstanceProfileName=profile_name,
                                        RoleName=role_name
                                    )
                                    logger.warning(f"Successfully removed role {role_name} from instance profile {profile_name}")
                                    
                                    # Also delete the instance profile
                                    logger.warning(f"Deleting instance profile {profile_name}")
                                    iam_client.delete_instance_profile(InstanceProfileName=profile_name)
                                    logger.warning(f"Successfully deleted instance profile {profile_name}")
                            except ClientError as e:
                                logger.error(f"Error handling instance profiles for role {role_name}: {str(e)}")
                            
                            logger.warning(f"Deleting IAM Role: {role_name}")
                            iam_client.delete_role(RoleName=role_name)
                            logger.warning(f"Successfully deleted IAM Role {role_name}")
                        except ClientError as e:
                            logger.error(f"Failed to delete IAM Role {role_name}: {str(e)}")
            
            if role_count == 0:
                logger.info("No IAM Roles found (excluding service-linked roles)")
        except ClientError as e:
            logger.error(f"Error listing IAM Roles: {str(e)}")
        
        # 9 & 10. Process IAM Policies (customer managed only)
        logger.info("Checking for customer-managed IAM Policies...")
        try:
            policy_paginator = iam_client.get_paginator('list_policies')
            policy_count = 0
            
            # Only get customer managed policies (Scope='Local')
            for page in policy_paginator.paginate(Scope='Local'):
                for policy in page['Policies']:
                    policy_count += 1
                    policy_name = policy['PolicyName']
                    policy_arn = policy['Arn']
                    
                    logger.info(f"Found customer-managed policy: {policy_name} (ARN: {policy_arn})")
                    
                    if not dry_run:
                        # First check if policy is attached to any entities
                        try:
                            entities = iam_client.list_entities_for_policy(PolicyArn=policy_arn)
                            
                            # If policy is attached to entities, we should have removed these attachments earlier
                            # But we can double-check here
                            has_attachments = False
                            
                            if entities.get('PolicyUsers', []):
                                has_attachments = True
                                for user in entities['PolicyUsers']:
                                    logger.warning(f"Detaching policy {policy_arn} from user {user['UserName']}")
                                    iam_client.detach_user_policy(UserName=user['UserName'], PolicyArn=policy_arn)
                            
                            if entities.get('PolicyGroups', []):
                                has_attachments = True
                                for group in entities['PolicyGroups']:
                                    logger.warning(f"Detaching policy {policy_arn} from group {group['GroupName']}")
                                    iam_client.detach_group_policy(GroupName=group['GroupName'], PolicyArn=policy_arn)
                            
                            if entities.get('PolicyRoles', []):
                                has_attachments = True
                                for role in entities['PolicyRoles']:
                                    logger.warning(f"Detaching policy {policy_arn} from role {role['RoleName']}")
                                    iam_client.detach_role_policy(RoleName=role['RoleName'], PolicyArn=policy_arn)
                            
                            if has_attachments:
                                logger.warning(f"Policy {policy_name} was still attached to entities, detached now")
                        except ClientError as e:
                            logger.error(f"Error checking attachments for policy {policy_name}: {str(e)}")
                        
                        # 9. Delete non-default versions of the policy first
                        try:
                            versions = iam_client.list_policy_versions(PolicyArn=policy_arn)
                            for version in versions.get('Versions', []):
                                # Skip the default version (we'll delete it with the policy itself)
                                if version['IsDefaultVersion']:
                                    continue
                                    
                                logger.warning(f"Deleting version {version['VersionId']} of policy {policy_name}")
                                iam_client.delete_policy_version(
                                    PolicyArn=policy_arn,
                                    VersionId=version['VersionId']
                                )
                                logger.warning(f"Successfully deleted version {version['VersionId']} of policy {policy_name}")
                        except ClientError as e:
                            logger.error(f"Error deleting versions for policy {policy_name}: {str(e)}")
                        
                        # 10. Delete the policy
                        try:
                            logger.warning(f"Deleting IAM Policy: {policy_name}")
                            iam_client.delete_policy(PolicyArn=policy_arn)
                            logger.warning(f"Successfully deleted IAM Policy {policy_name}")
                        except ClientError as e:
                            logger.error(f"Failed to delete IAM Policy {policy_name}: {str(e)}")
            
            if policy_count == 0:
                logger.info("No customer-managed IAM Policies found")
        except ClientError as e:
            logger.error(f"Error listing IAM Policies: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error cleaning IAM resources: {str(e)}")
        
    logger.info("Completed IAM resource cleanup")
        
 