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
                "Target Groups": "",
                "SSL Certificates": "",
            }

        formatted = {
            "Listener Protocols": [],
            "Listener Ports": [],
            "Target Groups": [],
            "SSL Certificates": [],
        }

        for listener in listeners:
            formatted["Listener Protocols"].append(listener.get("Protocol", "N/A"))
            formatted["Listener Ports"].append(str(listener.get("Port", "N/A")))

            # Format target groups
            if "DefaultActions" in listener:
                tg_names = []
                for action in listener["DefaultActions"]:
                    if action.get("Type") == "forward" and "TargetGroupArn" in action:
                        tg_name = action["TargetGroupArn"].split(":")[-1]
                        tg_names.append(tg_name)
                formatted["Target Groups"].append(",".join(tg_names) or "N/A")
            else:
                formatted["Target Groups"].append("N/A")

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
            "Target Groups": "; ".join(formatted["Target Groups"]),
            "SSL Certificates": "; ".join(formatted["SSL Certificates"]),
        }

    def get_resources(self, region):
        """Get all types of load balancers with target groups"""
        try:
            resources = []
            elbv2 = self.session.client("elbv2", region_name=region)
            ec2 = self.session.client("ec2", region_name=region)

            # Get Application and Network Load Balancers
            paginator = elbv2.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    # Get listeners and target groups
                    listeners = []
                    try:
                        listener_paginator = elbv2.get_paginator("describe_listeners")
                        for listener_page in listener_paginator.paginate(
                            LoadBalancerArn=lb["LoadBalancerArn"]
                        ):
                            for listener in listener_page["Listeners"]:
                                target_groups = []
                                for action in listener["DefaultActions"]:
                                    if "TargetGroupArn" in action:
                                        try:
                                            tg_response = elbv2.describe_target_groups(
                                                TargetGroupArns=[
                                                    action["TargetGroupArn"]
                                                ]
                                            )
                                            if tg_response["TargetGroups"]:
                                                tg = tg_response["TargetGroups"][0]
                                                targets = []
                                                target_health = (
                                                    elbv2.describe_target_health(
                                                        TargetGroupArn=action[
                                                            "TargetGroupArn"
                                                        ]
                                                    )
                                                )

                                                target_groups.append(
                                                    {
                                                        "TargetGroupName": tg[
                                                            "TargetGroupName"
                                                        ],
                                                        "Protocol": tg["Protocol"],
                                                        "Port": tg["Port"],
                                                        "TargetType": tg["TargetType"],
                                                    }
                                                )
                                        except ClientError:
                                            pass

                                listeners.append(
                                    {
                                        "Protocol": listener["Protocol"],
                                        "Port": listener["Port"],
                                        "TargetGroups": target_groups,
                                    }
                                )
                    except ClientError:
                        pass

                    listeners_info = self.format_listeners(listeners)

                    resources.append(
                        {
                            "Region": region,
                            "Service": "ELB",
                            "Resource Name": lb["LoadBalancerName"],
                            "Resource ID": lb["LoadBalancerArn"],
                            "Type": lb["Type"],
                            "DNS Name": lb["DNSName"],
                            "Scheme": lb["Scheme"],
                            "Listeners": listeners_info["Listener Protocols"]
                            + "; "
                            + listeners_info["Listener Ports"],
                            "Target Groups": listeners_info["Target Groups"],
                            "SSL Certificates": listeners_info["SSL Certificates"],
                        }
                    )

            return resources
        except ClientError as e:
            print(f"Error getting ELB resources in {region}: {str(e)}")
            return []
