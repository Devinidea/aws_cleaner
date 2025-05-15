"""
VPC Resource Cleaner Module
"""
import logging
import boto3
from botocore.exceptions import ClientError
import time

logger = logging.getLogger(__name__)

def clean(region, session, dry_run=True):
    """
    Clean VPC resources in the specified region
    
    Args:
        region (str): AWS region
        session (boto3.Session): Boto3 session
        dry_run (bool): If True, only simulate the cleanup
    """
    ec2_client = session.client('ec2', region_name=region)
    ec2_resource = session.resource('ec2', region_name=region)
    
    try:
        # Clean VPC resources in the following order:
        # 1. NAT Gateways
        # 2. Network Interfaces
        # 3. Internet Gateways
        # 4. VPN Connections
        # 5. VPN Gateways
        # 6. Transit Gateway Attachments
        # 7. Transit Gateways
        # 8. Subnet Route Table Associations
        # 9. Route Tables
        # 10. Subnets
        # 11. Security Groups (non-default)
        # 12. Network ACLs (non-default)
        # 13. VPC Endpoints
        # 14. VPC Peering Connections
        # 15. VPCs
        
        # 1. Delete NAT Gateways
        logger.info(f"Checking for NAT Gateways in {region}...")
        try:
            nat_gateways = ec2_client.describe_nat_gateways()
            
            if not nat_gateways['NatGateways']:
                logger.info(f"No NAT Gateways found in {region}")
            
            for nat in nat_gateways['NatGateways']:
                nat_id = nat['NatGatewayId']
                vpc_id = nat['VpcId']
                state = nat['State']
                
                # Skip already deleting/deleted NAT Gateways
                if state in ['deleting', 'deleted']:
                    logger.info(f"Skipping NAT Gateway {nat_id} as it's already {state}")
                    continue
                
                logger.info(f"Found NAT Gateway: {nat_id} (VPC: {vpc_id}, State: {state})")
                
                if not dry_run:
                    try:
                        logger.warning(f"Deleting NAT Gateway: {nat_id}")
                        ec2_client.delete_nat_gateway(NatGatewayId=nat_id)
                        logger.warning(f"Successfully initiated deletion for NAT Gateway {nat_id}")
                    except ClientError as e:
                        logger.error(f"Failed to delete NAT Gateway {nat_id}: {str(e)}")
        except ClientError as e:
            logger.error(f"Error listing NAT Gateways in {region}: {str(e)}")
        
        # 2. Delete Network Interfaces (ENIs)
        logger.info(f"Checking for Network Interfaces in {region}...")
        try:
            network_interfaces = ec2_client.describe_network_interfaces()
            
            if not network_interfaces['NetworkInterfaces']:
                logger.info(f"No Network Interfaces found in {region}")
            
            for eni in network_interfaces['NetworkInterfaces']:
                eni_id = eni['NetworkInterfaceId']
                status = eni['Status']
                description = eni.get('Description', 'N/A')
                
                # Skip interfaces that are already in use or being deleted
                if status in ['in-use', 'detaching', 'deleting']:
                    logger.info(f"Skipping Network Interface {eni_id} as it's {status}")
                    continue
                
                logger.info(f"Found Network Interface: {eni_id} (Status: {status}, Description: {description})")
                
                if not dry_run:
                    try:
                        logger.warning(f"Deleting Network Interface: {eni_id}")
                        ec2_client.delete_network_interface(NetworkInterfaceId=eni_id)
                        logger.warning(f"Successfully deleted Network Interface {eni_id}")
                    except ClientError as e:
                        logger.error(f"Failed to delete Network Interface {eni_id}: {str(e)}")
        except ClientError as e:
            logger.error(f"Error listing Network Interfaces in {region}: {str(e)}")
        
        # 3. Detach and Delete Internet Gateways
        logger.info(f"Checking for Internet Gateways in {region}...")
        try:
            internet_gateways = ec2_client.describe_internet_gateways()
            
            if not internet_gateways['InternetGateways']:
                logger.info(f"No Internet Gateways found in {region}")
            
            for igw in internet_gateways['InternetGateways']:
                igw_id = igw['InternetGatewayId']
                attachments = igw.get('Attachments', [])
                
                logger.info(f"Found Internet Gateway: {igw_id}")
                
                if not dry_run:
                    # Detach from all VPCs first
                    for attachment in attachments:
                        vpc_id = attachment.get('VpcId')
                        if vpc_id:
                            try:
                                logger.warning(f"Detaching Internet Gateway {igw_id} from VPC {vpc_id}")
                                ec2_client.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                                logger.warning(f"Successfully detached Internet Gateway {igw_id} from VPC {vpc_id}")
                            except ClientError as e:
                                logger.error(f"Failed to detach Internet Gateway {igw_id} from VPC {vpc_id}: {str(e)}")
                    
                    # Delete the Internet Gateway
                    try:
                        logger.warning(f"Deleting Internet Gateway: {igw_id}")
                        ec2_client.delete_internet_gateway(InternetGatewayId=igw_id)
                        logger.warning(f"Successfully deleted Internet Gateway {igw_id}")
                    except ClientError as e:
                        logger.error(f"Failed to delete Internet Gateway {igw_id}: {str(e)}")
        except ClientError as e:
            logger.error(f"Error listing Internet Gateways in {region}: {str(e)}")
        
        # 4. Delete VPN Connections
        logger.info(f"Checking for VPN Connections in {region}...")
        try:
            vpn_connections = ec2_client.describe_vpn_connections()
            
            if not vpn_connections['VpnConnections']:
                logger.info(f"No VPN Connections found in {region}")
            
            for vpn in vpn_connections['VpnConnections']:
                vpn_id = vpn['VpnConnectionId']
                state = vpn['State']
                
                # Skip connections that are already deleting/deleted
                if state in ['deleting', 'deleted']:
                    logger.info(f"Skipping VPN Connection {vpn_id} as it's already {state}")
                    continue
                
                logger.info(f"Found VPN Connection: {vpn_id} (State: {state})")
                
                if not dry_run:
                    try:
                        logger.warning(f"Deleting VPN Connection: {vpn_id}")
                        ec2_client.delete_vpn_connection(VpnConnectionId=vpn_id)
                        logger.warning(f"Successfully initiated deletion for VPN Connection {vpn_id}")
                    except ClientError as e:
                        logger.error(f"Failed to delete VPN Connection {vpn_id}: {str(e)}")
        except ClientError as e:
            logger.error(f"Error listing VPN Connections in {region}: {str(e)}")
        
        # 5. Delete VPN Gateways
        logger.info(f"Checking for VPN Gateways in {region}...")
        try:
            vpn_gateways = ec2_client.describe_vpn_gateways()
            
            if not vpn_gateways['VpnGateways']:
                logger.info(f"No VPN Gateways found in {region}")
            
            for vgw in vpn_gateways['VpnGateways']:
                vgw_id = vgw['VpnGatewayId']
                state = vgw['State']
                attachments = vgw.get('VpcAttachments', [])
                
                # Skip gateways that are already deleting/deleted
                if state in ['deleting', 'deleted']:
                    logger.info(f"Skipping VPN Gateway {vgw_id} as it's already {state}")
                    continue
                
                logger.info(f"Found VPN Gateway: {vgw_id} (State: {state})")
                
                if not dry_run:
                    # Detach from all VPCs first
                    for attachment in attachments:
                        vpc_id = attachment.get('VpcId')
                        attachment_state = attachment.get('State')
                        
                        if vpc_id and attachment_state not in ['detached', 'detaching']:
                            try:
                                logger.warning(f"Detaching VPN Gateway {vgw_id} from VPC {vpc_id}")
                                ec2_client.detach_vpn_gateway(VpnGatewayId=vgw_id, VpcId=vpc_id)
                                logger.warning(f"Successfully initiated detachment for VPN Gateway {vgw_id} from VPC {vpc_id}")
                            except ClientError as e:
                                logger.error(f"Failed to detach VPN Gateway {vgw_id} from VPC {vpc_id}: {str(e)}")
                    
                    # Wait a moment for detachments to process
                    time.sleep(5)
                    
                    # Delete the VPN Gateway
                    try:
                        logger.warning(f"Deleting VPN Gateway: {vgw_id}")
                        ec2_client.delete_vpn_gateway(VpnGatewayId=vgw_id)
                        logger.warning(f"Successfully deleted VPN Gateway {vgw_id}")
                    except ClientError as e:
                        logger.error(f"Failed to delete VPN Gateway {vgw_id}: {str(e)}")
        except ClientError as e:
            logger.error(f"Error listing VPN Gateways in {region}: {str(e)}")
        
        # 6. Delete Transit Gateway Attachments
        logger.info(f"Checking for Transit Gateway Attachments in {region}...")
        try:
            tgw_attachments = ec2_client.describe_transit_gateway_attachments()
            
            if not tgw_attachments.get('TransitGatewayAttachments'):
                logger.info(f"No Transit Gateway Attachments found in {region}")
            else:
                for attachment in tgw_attachments.get('TransitGatewayAttachments', []):
                    attachment_id = attachment['TransitGatewayAttachmentId']
                    state = attachment['State']
                    
                    # Skip attachments that are already deleting/deleted
                    if state in ['deleting', 'deleted']:
                        logger.info(f"Skipping Transit Gateway Attachment {attachment_id} as it's already {state}")
                        continue
                    
                    logger.info(f"Found Transit Gateway Attachment: {attachment_id} (State: {state})")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting Transit Gateway Attachment: {attachment_id}")
                            ec2_client.delete_transit_gateway_vpc_attachment(TransitGatewayAttachmentId=attachment_id)
                            logger.warning(f"Successfully initiated deletion for Transit Gateway Attachment {attachment_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete Transit Gateway Attachment {attachment_id}: {str(e)}")
        except ClientError as e:
            # Transit Gateway service might not be available in all regions
            if 'InvalidAction' in str(e) or 'UnauthorizedOperation' in str(e):
                logger.info(f"Transit Gateway service not available or not authorized in {region}")
            else:
                logger.error(f"Error listing Transit Gateway Attachments in {region}: {str(e)}")
        
        # 7. Delete Transit Gateways
        logger.info(f"Checking for Transit Gateways in {region}...")
        try:
            transit_gateways = ec2_client.describe_transit_gateways()
            
            if not transit_gateways.get('TransitGateways'):
                logger.info(f"No Transit Gateways found in {region}")
            else:
                for tgw in transit_gateways.get('TransitGateways', []):
                    tgw_id = tgw['TransitGatewayId']
                    state = tgw['State']
                    
                    # Skip gateways that are already deleting/deleted
                    if state in ['deleting', 'deleted']:
                        logger.info(f"Skipping Transit Gateway {tgw_id} as it's already {state}")
                        continue
                    
                    logger.info(f"Found Transit Gateway: {tgw_id} (State: {state})")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting Transit Gateway: {tgw_id}")
                            ec2_client.delete_transit_gateway(TransitGatewayId=tgw_id)
                            logger.warning(f"Successfully initiated deletion for Transit Gateway {tgw_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete Transit Gateway {tgw_id}: {str(e)}")
        except ClientError as e:
            # Transit Gateway service might not be available in all regions
            if 'InvalidAction' in str(e) or 'UnauthorizedOperation' in str(e):
                logger.info(f"Transit Gateway service not available or not authorized in {region}")
            else:
                logger.error(f"Error listing Transit Gateways in {region}: {str(e)}")
                
        # Get all VPCs to process their resources
        try:
            vpcs = ec2_client.describe_vpcs()
            
            if not vpcs['Vpcs']:
                logger.info(f"No VPCs found in {region}")
                return
                
            for vpc in vpcs['Vpcs']:
                vpc_id = vpc['VpcId']
                is_default = vpc.get('IsDefault', False)
                
                logger.info(f"Processing resources for VPC: {vpc_id} (Default: {is_default})")
                
                # 8 & 9. Delete Route Tables (disassociate first)
                logger.info(f"Checking for Route Tables in VPC {vpc_id}...")
                try:
                    route_tables = ec2_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
                    
                    for rt in route_tables['RouteTables']:
                        rt_id = rt['RouteTableId']
                        is_main = False
                        
                        # Check if this is the main route table (can't delete)
                        for association in rt.get('Associations', []):
                            if association.get('Main', False):
                                is_main = True
                                break
                        
                        if is_main:
                            logger.info(f"Skipping main route table {rt_id} for VPC {vpc_id}")
                            continue
                            
                        logger.info(f"Found Route Table: {rt_id} in VPC {vpc_id}")
                        
                        if not dry_run:
                            # Disassociate all subnets first
                            for association in rt.get('Associations', []):
                                if 'SubnetId' in association:
                                    association_id = association['RouteTableAssociationId']
                                    try:
                                        logger.warning(f"Disassociating Route Table {rt_id} from subnet")
                                        ec2_client.disassociate_route_table(AssociationId=association_id)
                                        logger.warning(f"Successfully disassociated Route Table {rt_id}")
                                    except ClientError as e:
                                        logger.error(f"Failed to disassociate Route Table {rt_id}: {str(e)}")
                            
                            # Delete the route table
                            try:
                                logger.warning(f"Deleting Route Table: {rt_id}")
                                ec2_client.delete_route_table(RouteTableId=rt_id)
                                logger.warning(f"Successfully deleted Route Table {rt_id}")
                            except ClientError as e:
                                logger.error(f"Failed to delete Route Table {rt_id}: {str(e)}")
                except ClientError as e:
                    logger.error(f"Error listing Route Tables for VPC {vpc_id}: {str(e)}")
                
                # 10. Delete Subnets
                logger.info(f"Checking for Subnets in VPC {vpc_id}...")
                try:
                    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
                    
                    for subnet in subnets['Subnets']:
                        subnet_id = subnet['SubnetId']
                        cidr = subnet['CidrBlock']
                        az = subnet['AvailabilityZone']
                        
                        logger.info(f"Found Subnet: {subnet_id} (CIDR: {cidr}, AZ: {az})")
                        
                        if not dry_run:
                            try:
                                logger.warning(f"Deleting Subnet: {subnet_id}")
                                ec2_client.delete_subnet(SubnetId=subnet_id)
                                logger.warning(f"Successfully deleted Subnet {subnet_id}")
                            except ClientError as e:
                                logger.error(f"Failed to delete Subnet {subnet_id}: {str(e)}")
                except ClientError as e:
                    logger.error(f"Error listing Subnets for VPC {vpc_id}: {str(e)}")
                
                # 11. Delete Security Groups (except default)
                logger.info(f"Checking for Security Groups in VPC {vpc_id}...")
                try:
                    security_groups = ec2_client.describe_security_groups(
                        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
                    )
                    
                    for sg in security_groups['SecurityGroups']:
                        sg_id = sg['GroupId']
                        sg_name = sg['GroupName']
                        
                        # Skip the default security group
                        if sg_name == 'default':
                            logger.info(f"Skipping default Security Group {sg_id} for VPC {vpc_id}")
                            continue
                            
                        logger.info(f"Found Security Group: {sg_id} (Name: {sg_name})")
                        
                        if not dry_run:
                            try:
                                logger.warning(f"Deleting Security Group: {sg_id}")
                                ec2_client.delete_security_group(GroupId=sg_id)
                                logger.warning(f"Successfully deleted Security Group {sg_id}")
                            except ClientError as e:
                                # This is expected if the SG is still in use
                                if "has a dependent object" in str(e) or "currently in use by" in str(e):
                                    logger.warning(f"Security Group {sg_id} is still in use, cannot delete now")
                                else:
                                    logger.error(f"Failed to delete Security Group {sg_id}: {str(e)}")
                except ClientError as e:
                    logger.error(f"Error listing Security Groups for VPC {vpc_id}: {str(e)}")
                
                # 12. Delete Network ACLs (except default)
                logger.info(f"Checking for Network ACLs in VPC {vpc_id}...")
                try:
                    network_acls = ec2_client.describe_network_acls(
                        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
                    )
                    
                    for acl in network_acls['NetworkAcls']:
                        acl_id = acl['NetworkAclId']
                        is_default = acl['IsDefault']
                        
                        if is_default:
                            logger.info(f"Skipping default Network ACL {acl_id} for VPC {vpc_id}")
                            continue
                            
                        logger.info(f"Found Network ACL: {acl_id}")
                        
                        if not dry_run:
                            try:
                                logger.warning(f"Deleting Network ACL: {acl_id}")
                                ec2_client.delete_network_acl(NetworkAclId=acl_id)
                                logger.warning(f"Successfully deleted Network ACL {acl_id}")
                            except ClientError as e:
                                # This is expected if the NACL is still in use
                                if "is being used by" in str(e):
                                    logger.warning(f"Network ACL {acl_id} is still in use, cannot delete now")
                                else:
                                    logger.error(f"Failed to delete Network ACL {acl_id}: {str(e)}")
                except ClientError as e:
                    logger.error(f"Error listing Network ACLs for VPC {vpc_id}: {str(e)}")
                
                # 13. Delete VPC Endpoints
                logger.info(f"Checking for VPC Endpoints in VPC {vpc_id}...")
                try:
                    vpc_endpoints = ec2_client.describe_vpc_endpoints(
                        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
                    )
                    
                    for endpoint in vpc_endpoints.get('VpcEndpoints', []):
                        endpoint_id = endpoint['VpcEndpointId']
                        endpoint_type = endpoint['VpcEndpointType']
                        service = endpoint['ServiceName']
                        
                        logger.info(f"Found VPC Endpoint: {endpoint_id} (Type: {endpoint_type}, Service: {service})")
                        
                        if not dry_run:
                            try:
                                logger.warning(f"Deleting VPC Endpoint: {endpoint_id}")
                                ec2_client.delete_vpc_endpoints(VpcEndpointIds=[endpoint_id])
                                logger.warning(f"Successfully initiated deletion for VPC Endpoint {endpoint_id}")
                            except ClientError as e:
                                logger.error(f"Failed to delete VPC Endpoint {endpoint_id}: {str(e)}")
                except ClientError as e:
                    logger.error(f"Error listing VPC Endpoints for VPC {vpc_id}: {str(e)}")
            
            # 14. Delete VPC Peering Connections
            logger.info(f"Checking for VPC Peering Connections in {region}...")
            try:
                vpc_peerings = ec2_client.describe_vpc_peering_connections()
                
                for peering in vpc_peerings.get('VpcPeeringConnections', []):
                    peering_id = peering['VpcPeeringConnectionId']
                    status = peering.get('Status', {}).get('Code', 'unknown')
                    
                    # Skip connections that are already deleting/deleted
                    if status in ['deleted', 'rejected', 'failed', 'expired']:
                        logger.info(f"Skipping VPC Peering Connection {peering_id} as it's already {status}")
                        continue
                    
                    accepter_vpc = peering.get('AccepterVpcInfo', {}).get('VpcId', 'unknown')
                    requester_vpc = peering.get('RequesterVpcInfo', {}).get('VpcId', 'unknown')
                    
                    logger.info(f"Found VPC Peering Connection: {peering_id} (Status: {status}, Between: {requester_vpc} and {accepter_vpc})")
                    
                    if not dry_run:
                        try:
                            logger.warning(f"Deleting VPC Peering Connection: {peering_id}")
                            ec2_client.delete_vpc_peering_connection(VpcPeeringConnectionId=peering_id)
                            logger.warning(f"Successfully deleted VPC Peering Connection {peering_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete VPC Peering Connection {peering_id}: {str(e)}")
            except ClientError as e:
                logger.error(f"Error listing VPC Peering Connections in {region}: {str(e)}")
            
            # 15. Delete VPCs
            logger.info(f"Deleting VPCs in {region}...")
            for vpc in vpcs['Vpcs']:
                vpc_id = vpc['VpcId']
                is_default = vpc.get('IsDefault', False)
                
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete VPC: {vpc_id} (Default: {is_default})")
                    continue
                
                # Skip default VPC if instructed (default VPCs are harder to recreate)
                if is_default:
                    logger.warning(f"Skipping default VPC {vpc_id}")
                    continue
                
                try:
                    logger.warning(f"Deleting VPC: {vpc_id}")
                    ec2_client.delete_vpc(VpcId=vpc_id)
                    logger.warning(f"Successfully deleted VPC {vpc_id}")
                except ClientError as e:
                    # This is expected if the VPC still has dependencies
                    if "has dependencies" in str(e) or "DependencyViolation" in str(e):
                        logger.warning(f"VPC {vpc_id} still has dependencies, cannot delete now")
                    else:
                        logger.error(f"Failed to delete VPC {vpc_id}: {str(e)}")
        
        except ClientError as e:
            logger.error(f"Error listing VPCs in {region}: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error cleaning VPC resources in {region}: {str(e)}")
        
    logger.info(f"Completed VPC resource cleanup in {region}") 