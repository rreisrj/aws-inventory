# aws_components/route53.py
from botocore.exceptions import ClientError


class Route53Component:
    def __init__(self, session):
        self.session = session

    def format_record_sets(self, record_sets):
        """Format record sets in a readable way"""
        if not record_sets:
            return {
                "Record Names": "",
                "Record Types": "",
                "Record Values": "",
                "Record TTLs": "",
            }

        formatted = {
            "Record Names": [],
            "Record Types": [],
            "Record Values": [],
            "Record TTLs": [],
        }

        for record in record_sets:
            formatted["Record Names"].append(record.get("Name", ""))
            formatted["Record Types"].append(record.get("Type", ""))

            # Format record values based on type
            values = []
            if "ResourceRecords" in record:
                values = [r.get("Value", "") for r in record["ResourceRecords"]]
            elif "AliasTarget" in record:
                values = [record["AliasTarget"].get("DNSName", "")]

            formatted["Record Values"].append(",".join(values) or "N/A")
            formatted["Record TTLs"].append(str(record.get("TTL", "N/A")))

        return {
            "Record Names": "; ".join(formatted["Record Names"]),
            "Record Types": "; ".join(formatted["Record Types"]),
            "Record Values": "; ".join(formatted["Record Values"]),
            "Record TTLs": "; ".join(formatted["Record TTLs"]),
        }

    def format_health_checks(self, health_checks):
        """Format health checks in a readable way"""
        if not health_checks:
            return "No health checks"

        formatted = []
        for check in health_checks:
            config = check.get("HealthCheckConfig", {})
            check_info = [
                f"ID: {check.get('Id', '')}",
                f"Type: {config.get('Type', '')}",
                f"Target: {config.get('IPAddress', config.get('FullyQualifiedDomainName', 'N/A'))}",
                f"Port: {config.get('Port', 'N/A')}",
                f"Path: {config.get('ResourcePath', 'N/A')}",
            ]
            formatted.append(" | ".join(check_info))

        return "\n".join(formatted)

    def get_resources(self, region):
        """Get Route53 resources information"""
        try:
            # Route53 is a global service, but we'll still track by region
            route53 = self.session.client("route53")
            route53_domains = self.session.client(
                "route53domains", region_name="us-east-1"
            )
            resources = []

            # Get hosted zones
            try:
                paginator = route53.get_paginator("list_hosted_zones")
                for page in paginator.paginate():
                    for zone in page["HostedZones"]:
                        # Get record sets for this zone
                        record_sets = []
                        try:
                            records_paginator = route53.get_paginator(
                                "list_resource_record_sets"
                            )
                            for records_page in records_paginator.paginate(
                                HostedZoneId=zone["Id"]
                            ):
                                record_sets.extend(records_page["ResourceRecordSets"])
                        except ClientError as e:
                            print(
                                f"Error getting record sets for zone {zone['Id']}: {str(e)}"
                            )

                        # Format record sets
                        records_info = self.format_record_sets(record_sets)

                        # Get zone tags
                        try:
                            tags = (
                                route53.list_tags_for_resource(
                                    ResourceType="hostedzone",
                                    ResourceId=zone["Id"].split("/")[-1],
                                )
                                .get("ResourceTagSet", {})
                                .get("Tags", [])
                            )
                        except ClientError:
                            tags = []

                        resources.append(
                            {
                                "Region": region,
                                "Service": "Route53",
                                "Resource Type": "Hosted Zone",
                                "Resource Name": zone["Name"],
                                "Resource ID": zone["Id"],
                                "Private Zone": zone["Config"]["PrivateZone"],
                                "Record Count": zone["ResourceRecordSetCount"],
                                **records_info,  # Add formatted record set columns
                                "Comment": zone.get("Config", {}).get("Comment", ""),
                                "Tags": str([{t["Key"]: t["Value"]} for t in tags]),
                            }
                        )
            except ClientError as e:
                print(f"Error getting hosted zones: {str(e)}")

            # Get health checks
            try:
                health_checks = []
                paginator = route53.get_paginator("list_health_checks")
                for page in paginator.paginate():
                    health_checks.extend(page["HealthChecks"])

                if health_checks:
                    resources.append(
                        {
                            "Region": region,
                            "Service": "Route53",
                            "Resource Type": "Health Checks",
                            "Resource Name": "Health Checks Summary",
                            "Resource ID": "N/A",
                            "Health Checks Count": len(health_checks),
                            "Health Checks": self.format_health_checks(health_checks),
                        }
                    )
            except ClientError as e:
                print(f"Error getting health checks: {str(e)}")

            # Get registered domains
            try:
                domains = []
                paginator = route53_domains.get_paginator("list_domains")
                for page in paginator.paginate():
                    for domain in page["Domains"]:
                        try:
                            # Get detailed domain information
                            detail = route53_domains.get_domain_detail(
                                DomainName=domain["DomainName"]
                            )
                            domains.append(
                                {
                                    "Name": domain["DomainName"],
                                    "AutoRenew": detail.get("AutoRenew", False),
                                    "ExpiryDate": str(detail.get("ExpirationDate", "")),
                                    "TransferLock": detail.get("TransferLock", False),
                                    "AdminContact": str(detail.get("AdminContact", {})),
                                    "RegistrantContact": str(
                                        detail.get("RegistrantContact", {})
                                    ),
                                }
                            )
                        except ClientError:
                            domains.append(
                                {
                                    "Name": domain["DomainName"],
                                    "Status": "Error getting details",
                                }
                            )

                if domains:
                    resources.append(
                        {
                            "Region": region,
                            "Service": "Route53",
                            "Resource Type": "Registered Domains",
                            "Resource Name": "Domains Summary",
                            "Resource ID": "N/A",
                            "Domain Count": len(domains),
                            "Domains": str(domains),
                        }
                    )
            except ClientError as e:
                print(f"Error getting registered domains: {str(e)}")

            return resources
        except ClientError as e:
            print(f"Error getting Route53 resources: {str(e)}")
            return []
