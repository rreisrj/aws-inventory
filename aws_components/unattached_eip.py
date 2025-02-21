# aws_components/unattached_eip.py
from botocore.exceptions import ClientError


class UnattachedEIPComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get unattached Elastic IP addresses information"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            unattached_eips = []

            # Get all Elastic IPs (no pagination needed)
            response = ec2.describe_addresses()

            for eip in response.get("Addresses", []):
                # Check if EIP is not associated with any instance or network interface
                if not eip.get("AssociationId"):
                    name = ""
                    for tag in eip.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    unattached_eips.append(
                        {
                            "Region": region,
                            "Service": "UnattachedEIP",
                            "Resource Name": name,
                            "Resource ID": eip["AllocationId"],
                            "Public IP": eip.get("PublicIp", ""),
                            "Private IP": eip.get("PrivateIpAddress", "Not assigned"),
                            "Domain": eip.get("Domain", ""),  # vpc or standard
                            "Network Border Group": eip.get("NetworkBorderGroup", ""),
                            "Allocation Time": str(eip.get("AllocationTime", "")),
                            "Public IPv4 Pool": eip.get("PublicIpv4Pool", "amazon"),
                            "Carrier IP": eip.get("CarrierIp", "N/A"),
                            "Customer Owned IP": eip.get("CustomerOwnedIp", "N/A"),
                            "Customer Owned IPv4 Pool": eip.get(
                                "CustomerOwnedIpv4Pool", "N/A"
                            ),
                            "Tags": str(
                                [{t["Key"]: t["Value"]} for t in eip.get("Tags", [])]
                            ),
                        }
                    )

            return unattached_eips
        except ClientError as e:
            print(f"Error getting unattached Elastic IPs in {region}: {str(e)}")
            return []
