# aws_components/ec2.py
from botocore.exceptions import ClientError


class EC2Component:
    def __init__(self, session):
        self.session = session

    def format_security_groups(self, security_groups):
        """Format security groups in a readable way"""
        return " | ".join(
            [f"{sg['GroupName']} ({sg['GroupId']})" for sg in security_groups]
        )

    def format_ebs_volumes(self, volumes):
        """Format EBS volumes in a readable way"""
        return " | ".join(
            [
                f"{vol['DeviceName']} ({vol['VolumeId']}) - {vol['Size']}GB {vol['VolumeType']}"
                for vol in volumes
            ]
        )

    def get_resources(self, region):
        """Get EC2 instances information with EBS volumes and security groups"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            instances = []

            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        name = ""
                        for tag in instance.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        # Get attached security groups
                        security_groups = []
                        for sg in instance.get("SecurityGroups", []):
                            security_groups.append(
                                {"GroupId": sg["GroupId"], "GroupName": sg["GroupName"]}
                            )

                        # Get attached EBS volumes with size
                        volumes = []
                        for volume in instance.get("BlockDeviceMappings", []):
                            if "Ebs" in volume:
                                vol_id = volume["Ebs"]["VolumeId"]
                                try:
                                    vol_info = ec2.describe_volumes(VolumeIds=[vol_id])[
                                        "Volumes"
                                    ][0]
                                    volumes.append(
                                        {
                                            "VolumeId": vol_id,
                                            "DeviceName": volume["DeviceName"],
                                            "Size": vol_info["Size"],
                                            "VolumeType": vol_info["VolumeType"],
                                        }
                                    )
                                except ClientError:
                                    continue

                        instances.append(
                            {
                                "Region": region,
                                "Service": "EC2",
                                "Resource Name": name,
                                "Resource ID": instance["InstanceId"],
                                "Instance Type": instance["InstanceType"],
                                "State": instance["State"]["Name"],
                                "Private IP": instance.get("PrivateIpAddress", ""),
                                "Public IP": instance.get("PublicIpAddress", ""),
                                "Security Groups": self.format_security_groups(
                                    security_groups
                                ),
                                "EBS Volumes": self.format_ebs_volumes(volumes),
                            }
                        )
            return instances
        except ClientError as e:
            print(f"Error getting EC2 resources in {region}: {str(e)}")
            return []
