# aws_components/gateway.py
from botocore.exceptions import ClientError


class GatewayComponent:
    def __init__(self, session):
        self.session = session

    def format_attachments(self, attachments):
        """Format gateway attachments in a readable way"""
        if not attachments:
            return {
                "Attachment VPCs": "",
                "Attachment States": "",
                "Attachment Types": "",
            }

        formatted = {
            "Attachment VPCs": [],
            "Attachment States": [],
            "Attachment Types": [],
        }

        for attachment in attachments:
            vpc_id = attachment.get("ResourceId", "")
            if (
                "ResourceDetails" in attachment
                and "VpcName" in attachment["ResourceDetails"]
            ):
                vpc_id = f"{vpc_id} ({attachment['ResourceDetails']['VpcName']})"

            formatted["Attachment VPCs"].append(vpc_id)
            formatted["Attachment States"].append(attachment.get("State", "N/A"))
            formatted["Attachment Types"].append(attachment.get("ResourceType", "N/A"))

        return {
            "Attachment VPCs": "; ".join(formatted["Attachment VPCs"]),
            "Attachment States": "; ".join(formatted["Attachment States"]),
            "Attachment Types": "; ".join(formatted["Attachment Types"]),
        }

    def get_resources(self, region):
        """Get gateway information including Internet, NAT, and Transit gateways"""
        gateways = []
        try:
            ec2 = self.session.client("ec2", region_name=region)
            print(f"Collecting Gateway resources in {region}...")

            # Get Internet Gateways
            try:
                igw_count = 0
                igw_paginator = ec2.get_paginator("describe_internet_gateways")
                for igw_page in igw_paginator.paginate():
                    for igw in igw_page["InternetGateways"]:
                        igw_count += 1
                        igw_name = next(
                            (
                                tag["Value"]
                                for tag in igw.get("Tags", [])
                                if tag["Key"] == "Name"
                            ),
                            "",
                        )
                        attachments = []
                        for att in igw.get("Attachments", []):
                            try:
                                vpc = ec2.describe_vpcs(VpcIds=[att["VpcId"]])["Vpcs"][
                                    0
                                ]
                                vpc_name = next(
                                    (
                                        tag["Value"]
                                        for tag in vpc.get("Tags", [])
                                        if tag["Key"] == "Name"
                                    ),
                                    "",
                                )
                                attachments.append(
                                    {
                                        "ResourceId": att["VpcId"],
                                        "ResourceType": "vpc",
                                        "State": att["State"],
                                        "ResourceDetails": {"VpcName": vpc_name},
                                    }
                                )
                            except ClientError:
                                attachments.append(
                                    {
                                        "ResourceId": att["VpcId"],
                                        "ResourceType": "vpc",
                                        "State": att["State"],
                                    }
                                )

                        attachments_info = self.format_attachments(attachments)
                        gateways.append(
                            {
                                "Region": region,
                                "Service": "Gateway",
                                "Type": "Internet Gateway",
                                "Resource Name": igw_name,
                                "Resource ID": igw["InternetGatewayId"],
                                "State": (
                                    "available"
                                    if igw.get("Attachments")
                                    else "detached"
                                ),
                                **attachments_info,
                                "Tags": ",".join(
                                    f"{t['Key']}={t['Value']}"
                                    for t in igw.get("Tags", [])
                                ),
                            }
                        )
                print(f"Found {igw_count} Internet Gateways in {region}")
            except ClientError as e:
                print(f"Error listing Internet Gateways in {region}: {str(e)}")

            # Get NAT Gateways
            try:
                nat_count = 0
                nat_paginator = ec2.get_paginator("describe_nat_gateways")
                for nat_page in nat_paginator.paginate():
                    for nat in nat_page["NatGateways"]:
                        nat_count += 1
                        nat_name = next(
                            (
                                tag["Value"]
                                for tag in nat.get("Tags", [])
                                if tag["Key"] == "Name"
                            ),
                            "",
                        )

                        # Get all IP addresses
                        private_ips = []
                        public_ips = []
                        for addr in nat.get("NatGatewayAddresses", []):
                            if addr.get("PrivateIp"):
                                private_ips.append(addr["PrivateIp"])
                            if addr.get("PublicIp"):
                                public_ips.append(addr["PublicIp"])

                        attachments = []
                        vpc_id = nat.get("VpcId", "")
                        if vpc_id:
                            try:
                                vpc = ec2.describe_vpcs(VpcIds=[vpc_id])["Vpcs"][0]
                                vpc_name = next(
                                    (
                                        tag["Value"]
                                        for tag in vpc.get("Tags", [])
                                        if tag["Key"] == "Name"
                                    ),
                                    "",
                                )
                                attachments.append(
                                    {
                                        "ResourceId": vpc_id,
                                        "ResourceType": "vpc",
                                        "State": nat.get("State", "unknown"),
                                        "ResourceDetails": {"VpcName": vpc_name},
                                    }
                                )
                            except ClientError:
                                attachments.append(
                                    {
                                        "ResourceId": vpc_id,
                                        "ResourceType": "vpc",
                                        "State": nat.get("State", "unknown"),
                                    }
                                )

                        attachments_info = self.format_attachments(attachments)
                        gateways.append(
                            {
                                "Region": region,
                                "Service": "Gateway",
                                "Type": "NAT Gateway",
                                "Resource Name": nat_name,
                                "Resource ID": nat["NatGatewayId"],
                                "State": nat.get("State", "unknown"),
                                "Private IPs": "; ".join(private_ips),
                                "Public IPs": "; ".join(public_ips),
                                "Subnet ID": nat.get("SubnetId", ""),
                                **attachments_info,
                                "Tags": ",".join(
                                    f"{t['Key']}={t['Value']}"
                                    for t in nat.get("Tags", [])
                                ),
                            }
                        )
                print(f"Found {nat_count} NAT Gateways in {region}")
            except ClientError as e:
                print(f"Error listing NAT Gateways in {region}: {str(e)}")

            # Get Transit Gateways
            try:
                tgw_count = 0
                ec2 = self.session.client("ec2", region_name=region)
                tgw_paginator = ec2.get_paginator("describe_transit_gateways")
                for tgw_page in tgw_paginator.paginate():
                    for tgw in tgw_page["TransitGateways"]:
                        tgw_count += 1
                        tgw_name = next(
                            (
                                tag["Value"]
                                for tag in tgw.get("Tags", [])
                                if tag["Key"] == "Name"
                            ),
                            "",
                        )

                        # Get Transit Gateway Attachments
                        attachments = []
                        try:
                            att_paginator = ec2.get_paginator(
                                "describe_transit_gateway_attachments"
                            )
                            for att_page in att_paginator.paginate(
                                Filters=[
                                    {
                                        "Name": "transit-gateway-id",
                                        "Values": [tgw["TransitGatewayId"]],
                                    }
                                ]
                            ):
                                for att in att_page["TransitGatewayAttachments"]:
                                    if att["ResourceType"] == "vpc":
                                        try:
                                            vpc = ec2.describe_vpcs(
                                                VpcIds=[att["ResourceId"]]
                                            )["Vpcs"][0]
                                            vpc_name = next(
                                                (
                                                    tag["Value"]
                                                    for tag in vpc.get("Tags", [])
                                                    if tag["Key"] == "Name"
                                                ),
                                                "",
                                            )
                                            attachments.append(
                                                {
                                                    "ResourceId": att["ResourceId"],
                                                    "ResourceType": att["ResourceType"],
                                                    "State": att["State"],
                                                    "ResourceDetails": {
                                                        "VpcName": vpc_name
                                                    },
                                                }
                                            )
                                        except ClientError:
                                            attachments.append(
                                                {
                                                    "ResourceId": att["ResourceId"],
                                                    "ResourceType": att["ResourceType"],
                                                    "State": att["State"],
                                                }
                                            )
                                    else:
                                        attachments.append(
                                            {
                                                "ResourceId": att["ResourceId"],
                                                "ResourceType": att["ResourceType"],
                                                "State": att["State"],
                                            }
                                        )
                        except ClientError as e:
                            print(
                                f"Error getting Transit Gateway attachments: {str(e)}"
                            )

                        attachments_info = self.format_attachments(attachments)
                        gateways.append(
                            {
                                "Region": region,
                                "Service": "Gateway",
                                "Type": "Transit Gateway",
                                "Resource Name": tgw_name,
                                "Resource ID": tgw["TransitGatewayId"],
                                "State": tgw.get("State", "unknown"),
                                "Owner ID": tgw.get("OwnerId", ""),
                                "Description": tgw.get("Description", ""),
                                **attachments_info,
                                "Tags": ",".join(
                                    f"{t['Key']}={t['Value']}"
                                    for t in tgw.get("Tags", [])
                                ),
                            }
                        )
                print(f"Found {tgw_count} Transit Gateways in {region}")
            except ClientError as e:
                print(f"Error listing Transit Gateways in {region}: {str(e)}")

            total_gateways = len(gateways)
            print(f"Total Gateway resources found in {region}: {total_gateways}")
            return gateways

        except Exception as e:
            print(f"Error in Gateway component for {region}: {str(e)}")
            return gateways
