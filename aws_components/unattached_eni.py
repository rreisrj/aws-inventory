# aws_components/unattached_eni.py
from botocore.exceptions import ClientError


class UnattachedENIComponent:
    def __init__(self, session):
        self.session = session

    def format_security_groups(self, security_groups):
        """Format security groups in a readable way"""
        return " | ".join(
            [
                f"{sg.get('GroupName', '')} ({sg.get('GroupId', '')})"
                for sg in security_groups
            ]
        )

    def format_private_ip_addresses(self, ip_addresses):
        """Format private IP addresses in a readable way"""
        return " | ".join(
            [
                f"{ip.get('PrivateIpAddress', '')} "
                f"({'Primary' if ip.get('Primary', False) else 'Secondary'})"
                for ip in ip_addresses
            ]
        )

    def get_resources(self, region):
        """Get unattached ENI information"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            unattached_enis = []

            # Get all ENIs
            paginator = ec2.get_paginator("describe_network_interfaces")
            for page in paginator.paginate():
                for eni in page["NetworkInterfaces"]:
                    # Check if ENI is not attached to any instance
                    if eni["Status"] == "available":
                        name = ""
                        for tag in eni.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        # Get security groups details
                        security_groups = []
                        for sg in eni.get("Groups", []):
                            try:
                                sg_details = ec2.describe_security_groups(
                                    GroupIds=[sg["GroupId"]]
                                )["SecurityGroups"][0]
                                security_groups.append(
                                    {
                                        "GroupId": sg["GroupId"],
                                        "GroupName": sg_details["GroupName"],
                                    }
                                )
                            except ClientError:
                                security_groups.append(
                                    {"GroupId": sg["GroupId"], "GroupName": "N/A"}
                                )

                        unattached_enis.append(
                            {
                                "Region": region,
                                "Service": "UnattachedENI",
                                "Resource Name": name,
                                "Resource ID": eni["NetworkInterfaceId"],
                                "Description": eni.get("Description", ""),
                                "Subnet ID": eni.get("SubnetId", ""),
                                "VPC ID": eni.get("VpcId", ""),
                                "Availability Zone": eni.get("AvailabilityZone", ""),
                                "MAC Address": eni.get("MacAddress", ""),
                                "Private IP Addresses": self.format_private_ip_addresses(
                                    eni.get("PrivateIpAddresses", [])
                                ),
                                "Private DNS Name": eni.get("PrivateDnsName", ""),
                                "Source/Dest Check": str(
                                    eni.get("SourceDestCheck", "")
                                ),
                                "Security Groups": self.format_security_groups(
                                    security_groups
                                ),
                                "Interface Type": eni.get("InterfaceType", ""),
                                "IPv6 Addresses": str(
                                    [
                                        ip["Ipv6Address"]
                                        for ip in eni.get("Ipv6Addresses", [])
                                    ]
                                ),
                                "Creation Time": str(eni.get("RequesterId", "")),
                                "Requester ID": eni.get("RequesterId", ""),
                                "Requester Managed": str(
                                    eni.get("RequesterManaged", False)
                                ),
                                "Status": eni.get("Status", ""),
                                "Tags": str(
                                    [
                                        {t["Key"]: t["Value"]}
                                        for t in eni.get("Tags", [])
                                    ]
                                ),
                            }
                        )

            return unattached_enis
        except ClientError as e:
            print(f"Error getting unattached ENIs in {region}: {str(e)}")
            return []
