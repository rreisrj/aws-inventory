# aws_components/unattached_sg.py
from botocore.exceptions import ClientError


class UnattachedSGComponent:
    def __init__(self, session):
        self.session = session

    def format_rules(self, rules):
        """Format security group rules in a readable way"""
        formatted_rules = []
        for rule in rules:
            ports = f"{rule.get('FromPort', 'All')}-{rule.get('ToPort', 'All')}"
            protocol = rule.get("IpProtocol", "-1")
            if protocol == "-1":
                protocol = "All"

            sources = []
            for ip_range in rule.get("IpRanges", []):
                description = (
                    f" ({ip_range.get('Description', '')})"
                    if ip_range.get("Description")
                    else ""
                )
                sources.append(f"{ip_range['CidrIp']}{description}")
            for ip_range in rule.get("Ipv6Ranges", []):
                description = (
                    f" ({ip_range.get('Description', '')})"
                    if ip_range.get("Description")
                    else ""
                )
                sources.append(f"{ip_range['CidrIpv6']}{description}")
            for group in rule.get("UserIdGroupPairs", []):
                sources.append(f"sg-{group['GroupId']}")

            formatted_rules.append(
                {"Ports": ports, "Protocol": protocol, "Sources/Destinations": sources}
            )
        return formatted_rules

    def is_sg_attached(self, ec2, sg_id, region):
        """
        Check if security group is attached to any resource
        Returns: (bool, str) - (is_attached, service_attached_to)
        """
        try:
            # 1. Check EC2 instances
            instances = ec2.describe_instances(
                Filters=[{"Name": "instance.group-id", "Values": [sg_id]}]
            )
            if any(instances["Reservations"]):
                return True, "EC2"

            # 2. Check RDS instances
            rds = self.session.client("rds", region_name=region)
            rds_instances = rds.describe_db_instances()
            for instance in rds_instances.get("DBInstances", []):
                for vpc_sg in instance.get("VpcSecurityGroups", []):
                    if vpc_sg.get("VpcSecurityGroupId") == sg_id:
                        return True, "RDS"

            # 3. Check ELB (Classic Load Balancer)
            elb = self.session.client("elb", region_name=region)
            lbs = elb.describe_load_balancers()
            for lb in lbs.get("LoadBalancerDescriptions", []):
                if sg_id in lb.get("SecurityGroups", []):
                    return True, "ELB"

            # 4. Check ALB/NLB (Application/Network Load Balancer)
            elbv2 = self.session.client("elbv2", region_name=region)
            lbsv2 = elbv2.describe_load_balancers()
            for lb in lbsv2.get("LoadBalancers", []):
                if sg_id in lb.get("SecurityGroups", []):
                    return True, "ALB/NLB"

            # 5. Check ElastiCache clusters
            elasticache = self.session.client("elasticache", region_name=region)
            clusters = elasticache.describe_cache_clusters(ShowCacheNodeInfo=True)
            for cluster in clusters.get("CacheClusters", []):
                if sg_id in [
                    sg["SecurityGroupId"] for sg in cluster.get("SecurityGroups", [])
                ]:
                    return True, "ElastiCache"

            # 6. Check EFS
            efs = self.session.client("efs", region_name=region)
            file_systems = efs.describe_file_systems()
            for fs in file_systems.get("FileSystems", []):
                mount_targets = efs.describe_mount_targets(
                    FileSystemId=fs["FileSystemId"]
                )
                for mt in mount_targets.get("MountTargets", []):
                    mt_sgs = efs.describe_mount_target_security_groups(
                        MountTargetId=mt["MountTargetId"]
                    )
                    if sg_id in mt_sgs.get("SecurityGroups", []):
                        return True, "EFS"

            # 7. Check Lambda functions
            lambda_client = self.session.client("lambda", region_name=region)
            functions = lambda_client.list_functions()
            for func in functions.get("Functions", []):
                if "VpcConfig" in func and sg_id in func["VpcConfig"].get(
                    "SecurityGroupIds", []
                ):
                    return True, "Lambda"

            # 8. Check ECS tasks/services
            ecs = self.session.client("ecs", region_name=region)
            clusters = ecs.list_clusters()
            for cluster_arn in clusters.get("clusterArns", []):
                services = ecs.list_services(cluster=cluster_arn)
                for service_arn in services.get("serviceArns", []):
                    service = ecs.describe_services(
                        cluster=cluster_arn, services=[service_arn]
                    )
                    for svc in service.get("services", []):
                        if "networkConfiguration" in svc:
                            if sg_id in svc["networkConfiguration"].get(
                                "awsvpcConfiguration", {}
                            ).get("securityGroups", []):
                                return True, "ECS"

            # 9. Check Redshift clusters
            redshift = self.session.client("redshift", region_name=region)
            clusters = redshift.describe_clusters()
            for cluster in clusters.get("Clusters", []):
                if sg_id in [
                    sg["VpcSecurityGroupId"]
                    for sg in cluster.get("VpcSecurityGroups", [])
                ]:
                    return True, "Redshift"

            # 10. Check for references from other VPCs (peering)
            references = ec2.describe_security_group_references(GroupId=[sg_id])
            if references.get("SecurityGroupReferenceSet"):
                return True, "VPC Peering"

            return False, None

        except ClientError as e:
            print(f"Error checking security group {sg_id}: {str(e)}")
            return False, None

    def get_resources(self, region):
        """Get unattached security groups information"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            security_groups = []

            # Get all security groups
            paginator = ec2.get_paginator("describe_security_groups")
            for page in paginator.paginate():
                for sg in page["SecurityGroups"]:
                    try:
                        # Check if the security group is attached to any resource
                        is_attached, attached_to = self.is_sg_attached(
                            ec2, sg["GroupId"], region
                        )

                        # Skip if the security group is attached
                        if is_attached:
                            continue

                        # Format inbound and outbound rules
                        inbound_rules = self.format_rules(sg["IpPermissions"])
                        outbound_rules = self.format_rules(sg["IpPermissionsEgress"])

                        security_groups.append(
                            {
                                "Region": region,
                                "Service": "UnattachedSG",
                                "Resource Name": sg["GroupName"],
                                "Resource ID": sg["GroupId"],
                                "VPC ID": sg.get("VpcId", "Default VPC"),
                                "Description": sg["Description"],
                                "Inbound Rules": str(inbound_rules),
                                "Outbound Rules": str(outbound_rules),
                                "Tags": str(
                                    [{t["Key"]: t["Value"]} for t in sg.get("Tags", [])]
                                ),
                                "Created By": next(
                                    (
                                        t["Value"]
                                        for t in sg.get("Tags", [])
                                        if t["Key"] == "CreatedBy"
                                    ),
                                    "N/A",
                                ),
                                "Created Date": next(
                                    (
                                        t["Value"]
                                        for t in sg.get("Tags", [])
                                        if t["Key"] == "CreatedDate"
                                    ),
                                    "N/A",
                                ),
                            }
                        )
                    except ClientError:
                        continue

            return security_groups
        except ClientError as e:
            print(f"Error getting unattached security groups in {region}: {str(e)}")
            return []
