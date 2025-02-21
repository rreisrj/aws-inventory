# aws_components/rds.py
from botocore.exceptions import ClientError


class RDSComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get RDS instances information"""
        try:
            rds = self.session.client("rds", region_name=region)
            instances = []

            # Get DB instances
            paginator = rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for instance in page["DBInstances"]:
                    # Get security groups
                    security_groups = []
                    for sg in instance.get("VpcSecurityGroups", []):
                        security_groups.append(
                            {
                                "GroupId": sg.get("VpcSecurityGroupId", ""),
                                "Status": sg.get("Status", ""),
                            }
                        )

                    # Get read replicas
                    read_replicas = instance.get("ReadReplicaDBInstanceIdentifiers", [])

                    # Get backup information
                    backup_info = {
                        "Window": instance.get("PreferredBackupWindow", "N/A"),
                        "RetentionPeriod": instance.get("BackupRetentionPeriod", 0),
                        "LatestBackup": str(
                            instance.get("LatestRestorableTime", "N/A")
                        ),
                    }

                    # Get endpoint information safely
                    endpoint = instance.get("Endpoint", {})
                    endpoint_address = endpoint.get("Address", "") if endpoint else ""
                    endpoint_port = endpoint.get("Port", "") if endpoint else ""

                    # Get subnet group information safely
                    subnet_group = instance.get("DBSubnetGroup", {})
                    vpc_id = subnet_group.get("VpcId", "") if subnet_group else ""
                    subnet_group_name = (
                        subnet_group.get("DBSubnetGroupName", "")
                        if subnet_group
                        else ""
                    )

                    # Get performance insights status
                    performance_insights = "Disabled"
                    if instance.get("PerformanceInsightsEnabled", False):
                        performance_insights = {
                            "RetentionPeriod": instance.get(
                                "PerformanceInsightsRetentionPeriod", 0
                            ),
                            "KMSKeyId": instance.get(
                                "PerformanceInsightsKMSKeyId", "N/A"
                            ),
                        }

                    instances.append(
                        {
                            "Region": region,
                            "Service": "RDS",
                            "Resource Name": instance.get("DBInstanceIdentifier", ""),
                            "Resource ID": instance.get("DBInstanceIdentifier", ""),
                            "Engine": instance.get("Engine", ""),
                            "Engine Version": instance.get("EngineVersion", ""),
                            "Instance Class": instance.get("DBInstanceClass", ""),
                            "Status": instance.get("DBInstanceStatus", ""),
                            "Multi-AZ": instance.get("MultiAZ", False),
                            "Storage Type": instance.get("StorageType", ""),
                            "Allocated Storage": instance.get("AllocatedStorage", 0),
                            "Endpoint": endpoint_address,
                            "Port": endpoint_port,
                            "Security Groups": str(security_groups),
                            "Read Replicas": str(read_replicas),
                            "Backup Info": str(backup_info),
                            "Performance Insights": str(performance_insights),
                            "VPC ID": vpc_id,
                            "Subnet Group": subnet_group_name,
                        }
                    )

            return instances
        except ClientError as e:
            print(f"Error getting RDS resources in {region}: {str(e)}")
            return []
