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
                    subnet_names = []
                    subnet_ids = []
                    subnet_cidrs = []
                    subnet_azs = []
                    subnet_az_ids = []
                    subnet_az_types = []
                    subnet_az_states = []
                    subnet_states = []
                    subnet_ips = []

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
                                    "No Name",
                                )
                                az_name = subnet["AvailabilityZone"]
                                az_info = available_azs.get(az_name, {})

                                subnet_names.append(subnet_name)
                                subnet_ids.append(subnet["SubnetId"])
                                subnet_cidrs.append(subnet["CidrBlock"])
                                subnet_azs.append(az_name)
                                subnet_az_ids.append(az_info.get("ZoneId", "N/A"))
                                subnet_az_types.append(az_info.get("ZoneType", "N/A"))
                                subnet_az_states.append(az_info.get("State", "N/A"))
                                subnet_states.append(subnet["State"])
                                subnet_ips.append(
                                    str(subnet["AvailableIpAddressCount"])
                                )
                    except ClientError:
                        pass

                    vpcs.append(
                        {
                            "Region": region,
                            "Service": "VPC",
                            "Resource Name": vpc_name,
                            "Resource ID": vpc["VpcId"],
                            "CIDR": vpc["CidrBlock"],
                            "State": vpc["State"],
                            "Is Default": vpc["IsDefault"],
                            "Subnet Names": (
                                "; ".join(subnet_names) if subnet_names else "N/A"
                            ),
                            "Subnet IDs": (
                                "; ".join(subnet_ids) if subnet_ids else "N/A"
                            ),
                            "Subnet CIDRs": (
                                "; ".join(subnet_cidrs) if subnet_cidrs else "N/A"
                            ),
                            "Subnet AZs": (
                                "; ".join(subnet_azs) if subnet_azs else "N/A"
                            ),
                            "Subnet AZ IDs": (
                                "; ".join(subnet_az_ids) if subnet_az_ids else "N/A"
                            ),
                            "Subnet AZ Types": (
                                "; ".join(subnet_az_types) if subnet_az_types else "N/A"
                            ),
                            "Subnet AZ States": (
                                "; ".join(subnet_az_states)
                                if subnet_az_states
                                else "N/A"
                            ),
                            "Subnet States": (
                                "; ".join(subnet_states) if subnet_states else "N/A"
                            ),
                            "Subnet Available IPs": (
                                "; ".join(subnet_ips) if subnet_ips else "N/A"
                            ),
                        }
                    )

            print(f"  Found {len(vpcs)} VPC resources in {region}")
            return vpcs
        except ClientError as e:
            print(f"Error getting VPC resources in {region}: {str(e)}")
            return []
