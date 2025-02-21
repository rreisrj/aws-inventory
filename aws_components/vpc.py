# aws_components/vpc.py
from botocore.exceptions import ClientError


class VPCComponent:
    def __init__(self, session):
        self.session = session

    def format_subnets(self, subnets):
        """Format subnets in a readable way with line breaks"""
        formatted_subnets = []
        for subnet in subnets:
            subnet_info = [
                f"Name: {subnet['Name'] or 'No Name'}",
                f"ID: {subnet['SubnetId']}",
                f"CIDR: {subnet['CIDR']}",
                f"AZ: {subnet['AZ']}",
                f"State: {subnet['State']}",
                f"Available IPs: {subnet['Available IPs']}",
            ]
            formatted_subnets.append(" | ".join(subnet_info))

        # Join different subnets with a line break
        return "\n".join(formatted_subnets)

    def get_resources(self, region):
        """Get VPC information including subnets and peering connections"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            vpcs = []

            # Get VPCs
            vpc_paginator = ec2.get_paginator("describe_vpcs")
            for vpc_page in vpc_paginator.paginate():
                for vpc in vpc_page["Vpcs"]:
                    vpc_name = next(
                        (
                            tag["Value"]
                            for tag in vpc.get("Tags", [])
                            if tag["Key"] == "Name"
                        ),
                        "",
                    )

                    # Get subnets for this VPC
                    subnets = []
                    try:
                        subnet_paginator = ec2.get_paginator("describe_subnets")
                        for subnet_page in subnet_paginator.paginate(
                            Filters=[{"Name": "vpc-id", "Values": [vpc["VpcId"]]}]
                        ):
                            for subnet in subnet_page["Subnets"]:
                                subnet_name = next(
                                    (
                                        tag["Value"]
                                        for tag in subnet.get("Tags", [])
                                        if tag["Key"] == "Name"
                                    ),
                                    "",
                                )
                                subnets.append(
                                    {
                                        "SubnetId": subnet["SubnetId"],
                                        "Name": subnet_name,
                                        "CIDR": subnet["CidrBlock"],
                                        "AZ": subnet["AvailabilityZone"],
                                        "State": subnet["State"],
                                        "Available IPs": subnet[
                                            "AvailableIpAddressCount"
                                        ],
                                    }
                                )
                    except ClientError:
                        pass

                    # [Rest of the VPC code remains the same]
                    vpcs.append(
                        {
                            "Region": region,
                            "Service": "VPC",
                            "Resource Name": vpc_name,
                            "Resource ID": vpc["VpcId"],
                            "CIDR": vpc["CidrBlock"],
                            "State": vpc["State"],
                            "Is Default": vpc["IsDefault"],
                            "Subnets": self.format_subnets(subnets),
                            # [Rest of the fields remain the same]
                        }
                    )

            return vpcs
        except ClientError as e:
            print(f"Error getting VPC resources in {region}: {str(e)}")
            return []
