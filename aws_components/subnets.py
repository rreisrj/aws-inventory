# aws_components/subnets.py
from botocore.exceptions import ClientError


class SubnetComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get subnet information including AZ details"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            subnets = []

            # Get all available AZs in the region
            try:
                az_response = ec2.describe_availability_zones()
                available_azs = {
                    az["ZoneName"]: {
                        "State": az["State"],
                        "ZoneId": az["ZoneId"],
                        "ZoneType": az.get("ZoneType", "N/A"),
                    }
                    for az in az_response["AvailabilityZones"]
                }
            except ClientError:
                available_azs = {}

            # Get all subnets
            subnet_paginator = ec2.get_paginator("describe_subnets")
            for subnet_page in subnet_paginator.paginate():
                for subnet in subnet_page["Subnets"]:
                    # Get subnet name from tags
                    subnet_name = next(
                        (
                            tag["Value"]
                            for tag in subnet.get("Tags", [])
                            if tag["Key"] == "Name"
                        ),
                        "No Name",
                    )

                    az_name = subnet["AvailabilityZone"]
                    az_info = available_azs.get(az_name, {})

                    subnets.append(
                        {
                            "Region": region,
                            "Service": "Subnets",
                            "Subnet Name": subnet_name,
                            "Resource ID": subnet["SubnetId"],
                            "VPC ID": subnet["VpcId"],
                            "CIDR": subnet["CidrBlock"],
                            "Available IPs": subnet["AvailableIpAddressCount"],
                            "Auto Assign Public IP": subnet.get(
                                "MapPublicIpOnLaunch", False
                            ),
                            "AZ Name": az_name,
                            "AZ ID": az_info.get("ZoneId", "N/A"),
                        }
                    )

            print(f"  Found {len(subnets)} subnet resources in {region}")
            return subnets
        except ClientError as e:
            print(f"Error getting subnet resources in {region}: {str(e)}")
            return []
