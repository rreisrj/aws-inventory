# aws_components/elb.py
from botocore.exceptions import ClientError


class ELBComponent:
    def __init__(self, session):
        self.session = session

    def format_target_groups(self, target_groups):
        """Format target groups in a readable way"""
        if not target_groups:
            return "No target groups"

        formatted_tgs = []
        for tg in target_groups:
            tg_info = [
                f"Name: {tg['TargetGroupName']}",
                f"Protocol: {tg['Protocol']}",
                f"Port: {tg['Port']}",
                f"Type: {tg['TargetType']}",
            ]
            formatted_tgs.append(" | ".join(tg_info))
        return "\n  " + "\n  ".join(formatted_tgs)

    def format_listeners(self, listeners):
        """Format listeners in a readable way"""
        if not listeners:
            return {
                "Listener Protocols": "",
                "Listener Ports": "",
                "SSL Certificates": "",
            }

        formatted = {
            "Listener Protocols": [],
            "Listener Ports": [],
            "SSL Certificates": [],
        }

        for listener in listeners:
            formatted["Listener Protocols"].append(listener.get("Protocol", "N/A"))
            formatted["Listener Ports"].append(str(listener.get("Port", "N/A")))

            # Format SSL certificates
            if "Certificates" in listener:
                cert_ids = [
                    cert.get("CertificateArn", "").split("/")[-1]
                    for cert in listener["Certificates"]
                ]
                formatted["SSL Certificates"].append(",".join(cert_ids) or "N/A")
            else:
                formatted["SSL Certificates"].append("N/A")

        return {
            "Listener Protocols": "; ".join(formatted["Listener Protocols"]),
            "Listener Ports": "; ".join(formatted["Listener Ports"]),
            "SSL Certificates": "; ".join(formatted["SSL Certificates"]),
        }

    def get_target_groups(self, elbv2_client, lb_arn):
        """Get target groups for a load balancer"""
        try:
            tg_paginator = elbv2_client.get_paginator("describe_target_groups")
            target_groups = []
            for page in tg_paginator.paginate(LoadBalancerArn=lb_arn):
                target_groups.extend(page["TargetGroups"])
            return target_groups
        except ClientError as e:
            print(f"Error getting target groups for {lb_arn}: {str(e)}")
            return []

    def get_resources(self, region):
        """Get all types of load balancers with target groups"""
        try:
            resources = []
            elbv2 = self.session.client("elbv2", region_name=region)
            print(f"Collecting ELB resources in {region}...")

            paginator = elbv2.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    lb_arn = lb["LoadBalancerArn"]

                    # Get target groups with full details
                    target_groups = self.get_target_groups(elbv2, lb_arn)

                    # Get listeners
                    listeners = []
                    try:
                        listener_paginator = elbv2.get_paginator("describe_listeners")
                        for listener_page in listener_paginator.paginate(
                            LoadBalancerArn=lb_arn
                        ):
                            listeners.extend(listener_page["Listeners"])
                    except ClientError:
                        pass

                    # Format all information
                    listeners_info = self.format_listeners(listeners)
                    target_groups_summary = self.format_target_groups(target_groups)

                    # Get target group names and IDs for dependency mapping
                    tg_names = [tg["TargetGroupName"] for tg in target_groups]
                    tg_ids = [tg["TargetGroupArn"] for tg in target_groups]

                    resources.append(
                        {
                            "Region": region,
                            "Service": "ELB",
                            "Resource Name": lb["LoadBalancerName"],
                            "Resource ID": lb_arn,
                            "Type": lb["Type"],
                            "DNS Name": lb["DNSName"],
                            "Scheme": lb["Scheme"],
                            "VPC ID": lb.get("VpcId", "N/A"),
                            "Listeners": listeners_info["Listener Protocols"]
                            + "; "
                            + listeners_info["Listener Ports"],
                            "SSL Certificates": listeners_info["SSL Certificates"],
                            "Target Groups": target_groups_summary,
                            "Target Group Names": "; ".join(tg_names) or "N/A",
                            "Target Group IDs": "; ".join(tg_ids) or "N/A",
                        }
                    )

            print(f"  Found {len(resources)} ELB resources in {region}")
            return resources
        except ClientError as e:
            print(f"Error collecting ELB resources in {region}: {str(e)}")
            return []
