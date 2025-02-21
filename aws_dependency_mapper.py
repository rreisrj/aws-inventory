#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd


class AWSDependencyMapper:
    def __init__(self, excel_file):
        """Initialize the mapper with the path to the Excel inventory file"""
        self.excel_file = Path(excel_file)
        if not self.excel_file.exists():
            raise FileNotFoundError(f"Inventory file not found: {excel_file}")
        self.sheets = {}
        self.load_excel_data()

    def load_excel_data(self):
        """Load all sheets from the Excel file into dataframes"""
        try:
            xlsx = pd.ExcelFile(self.excel_file)
            print(f"\nAvailable sheets in inventory: {xlsx.sheet_names}")
            for sheet_name in xlsx.sheet_names:
                if sheet_name != "Summary":  # Skip the summary sheet
                    self.sheets[sheet_name] = pd.read_excel(xlsx, sheet_name)
                    print(
                        f"Loaded sheet: {sheet_name} with {len(self.sheets[sheet_name])} rows"
                    )
        except Exception as e:
            raise Exception(f"Error loading Excel file: {str(e)}")

    def get_load_balancer_topology(self):
        """Get complete topology for each load balancer"""
        topologies = {}

        if "ELB" not in self.sheets:
            print(
                "\nNo ELB sheet found in inventory. Available sheets:",
                list(self.sheets.keys()),
            )
            return topologies

        elbs = self.sheets["ELB"]
        print(f"\nFound {len(elbs)} load balancers")
        print("Available columns:", list(elbs.columns))

        for _, elb in elbs.iterrows():
            try:
                lb_name = elb.get("Resource Name", "N/A")
                lb_id = elb.get("Resource ID", "N/A")
                region = elb.get("Region", "N/A")
                print(f"\nProcessing LB: {lb_name} ({lb_id}) in {region}")

                # Check different possible VPC ID field names
                vpc_id = None
                for field in ["VpcId", "VPC ID", "VPC Id", "Vpc ID"]:
                    if field in elb and pd.notna(elb[field]):
                        vpc_id = elb[field]
                        print(f"Found VPC ID in field '{field}': {vpc_id}")
                        break

                if not vpc_id:
                    print(f"Warning: No VPC ID found for LB {lb_name}")
                    vpc_id = "N/A"

                topology = {
                    "LoadBalancer": {
                        "Name": lb_name,
                        "ID": lb_id,
                        "Type": elb.get("Type", "N/A"),
                        "DNS": elb.get("DNSName", elb.get("DNS Name", "N/A")),
                        "Scheme": elb.get("Scheme", "N/A"),
                        "IsInternetFacing": elb.get("IsInternetFacing", False),
                    },
                    "Gateway": self.get_gateway_for_vpc(region, vpc_id),
                    "TargetGroups": self.get_target_groups(region, lb_id),
                    "Region": region,
                    "VPC": vpc_id,
                }

                sheet_name = f"{region}_{lb_name}"[:31]  # Excel sheet name length limit
                print(f"Created topology for sheet: {sheet_name}")
                topologies[sheet_name] = topology
            except Exception as e:
                print(f"Warning: Skipping load balancer due to error: {str(e)}")
                continue

        print(f"\nCreated {len(topologies)} topology sheets")
        return topologies

    def get_gateway_for_vpc(self, region, vpc_id):
        """Get Internet Gateway information for the VPC"""
        if "Gateway" in self.sheets:
            gateways = self.sheets["Gateway"]
            vpc_gateways = gateways[
                (gateways["Region"] == region)
                & (
                    (gateways.get("VpcId") == vpc_id)
                    | (gateways.get("VPC ID") == vpc_id)
                    | (gateways.get("VPC Id") == vpc_id)
                    | (gateways.get("Vpc ID") == vpc_id)
                )
            ]

            if not vpc_gateways.empty:
                gateway = vpc_gateways.iloc[0]
                return {
                    "Name": gateway.get("Resource Name", "N/A"),
                    "ID": gateway.get("Resource ID", "N/A"),
                    "Type": gateway.get("Type", "N/A"),
                    "State": gateway.get("State", "N/A"),
                    "VPC Attachments": gateway.get("VPC Attachments", "N/A"),
                }
        return {
            "Name": "N/A",
            "ID": "N/A",
            "Type": "N/A",
            "State": "N/A",
            "VPC Attachments": "N/A",
        }

    def get_target_groups(self, region, lb_arn):
        """Get target groups and their instances for the load balancer"""
        target_groups = []

        if "TargetGroup" in self.sheets:
            tgs = self.sheets["TargetGroup"]
            try:
                lb_tgs = tgs[tgs["LoadBalancerArns"].str.contains(lb_arn, na=False)]

                for _, tg in lb_tgs.iterrows():
                    try:
                        target_info = tg.get("Targets", "")
                        target_ports = tg.get("Target Ports", "")
                        instances = self.get_instances(target_info)

                        tg_data = {
                            "Name": tg.get("Resource Name", "N/A"),
                            "ID": tg.get("Resource ID", "N/A"),
                            "Protocol": tg.get("Protocol", "N/A"),
                            "Port": tg.get("Port", "N/A"),
                            "HealthCheckProtocol": tg.get("HealthCheckProtocol", "N/A"),
                            "TargetType": tg.get("TargetType", "N/A"),
                            "Targets": target_info if target_info != "N/A" else [],
                            "Target Ports": (
                                target_ports if target_ports != "N/A" else []
                            ),
                            "Instances": instances,
                            "Databases": self.get_databases_for_instances(instances),
                        }
                        target_groups.append(tg_data)
                    except Exception as e:
                        print(f"Warning: Error processing target group: {str(e)}")
                        continue
            except Exception as e:
                print(f"Warning: Error filtering target groups: {str(e)}")

        return target_groups

    def get_instances(self, target_info):
        """Extract instance information from target info"""
        instances = []

        if not isinstance(target_info, str) or not target_info.strip():
            return instances

        # Split the target info by newlines to handle the new format
        targets = [t.strip() for t in target_info.split("\n") if t.strip()]

        if "EC2" in self.sheets:
            ec2s = self.sheets["EC2"]
            for target in targets:
                # Extract instance ID or IP from the new format "id_or_ip (health_status)"
                target_id = target.split(" (")[0] if " (" in target else target

                # Try to find the instance by ID, name, or IP
                instance_matches = ec2s[
                    ec2s["Resource ID"].str.contains(target_id, na=False, regex=False)
                    | ec2s["Resource Name"].str.contains(
                        target_id, na=False, regex=False
                    )
                    | ec2s["Private IP"].str.contains(target_id, na=False, regex=False)
                ]

                if not instance_matches.empty:
                    instance = instance_matches.iloc[0]
                    instances.append(
                        {
                            "Name": instance.get("Resource Name", "N/A"),
                            "ID": instance.get("Resource ID", "N/A"),
                            "Type": instance.get("Instance Type", "N/A"),
                            "State": instance.get("State", "N/A"),
                            "Private IP": instance.get("Private IP", "N/A"),
                            "Target Health": (
                                target.split(" (")[1].rstrip(")")
                                if " (" in target
                                else "N/A"
                            ),
                        }
                    )

        print(f"Found {len(instances)} instances for target info")
        return instances

    def get_databases_for_instances(self, instances):
        """Get RDS instances sharing security groups with the EC2/EKS instances"""
        databases = []

        if "RDS" not in self.sheets or not instances:
            return databases

        rds = self.sheets["RDS"]
        instance_sgs = set()
        for instance in instances:
            sgs = instance.get("SecurityGroups", "").split(",")
            instance_sgs.update(sg.strip() for sg in sgs if sg.strip())

        for _, db in rds.iterrows():
            db_sgs = str(db.get("Security Groups", "")).split(",")
            db_sgs = {sg.strip() for sg in db_sgs if sg.strip()}

            if instance_sgs & db_sgs:  # If there are common security groups
                db_data = {
                    "Name": db.get("Resource Name", "N/A"),
                    "ID": db.get("Resource ID", "N/A"),
                    "Endpoint": db.get("Endpoint", "N/A"),
                    "Type": db.get("Engine", "N/A"),
                    "SecurityGroups": ", ".join(db_sgs),
                }
                databases.append(db_data)

        return databases

    def export_dependencies(self, output_file):
        """Export the dependency mapping to a new Excel file"""
        try:
            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                topologies = self.get_load_balancer_topology()

                if not topologies:
                    df = pd.DataFrame(
                        {
                            "Resource Type": ["Information"],
                            "Name": ["No Load Balancers Found"],
                            "ID": ["N/A"],
                            "Additional Info": [
                                "No load balancers were found in the AWS inventory."
                            ],
                        }
                    )
                    df.to_excel(writer, sheet_name="No Load Balancers", index=False)
                    worksheet = writer.sheets["No Load Balancers"]
                    for idx, col in enumerate(df.columns):
                        worksheet.column_dimensions[chr(65 + idx)].width = 50
                    print("Warning: No load balancers found in the inventory.")
                    return

                for sheet_name, topology in topologies.items():
                    try:
                        rows = []

                        # Add Gateway info first (if exists)
                        gateway = topology["Gateway"]
                        if gateway["ID"] != "N/A":
                            rows.append(
                                {
                                    "Resource Type": "Internet Gateway",
                                    "Name": gateway["Name"],
                                    "ID": gateway["ID"],
                                    "Additional Info": f"Type: {gateway['Type']}, State: {gateway['State']}, VPC Attachments: {gateway['VPC Attachments']}",
                                }
                            )

                        # Add Load Balancer info with scheme
                        lb = topology["LoadBalancer"]
                        scheme_info = (
                            "Internet-Facing"
                            if lb.get("IsInternetFacing")
                            else "Internal"
                        )
                        rows.append(
                            {
                                "Resource Type": "Load Balancer",
                                "Name": lb["Name"],
                                "ID": lb["ID"],
                                "Additional Info": f"Type: {lb['Type']}, Scheme: {scheme_info}, DNS: {lb['DNS']}",
                            }
                        )

                        # Add Target Groups and related resources
                        for tg in topology["TargetGroups"]:
                            rows.append(
                                {
                                    "Resource Type": "Target Group",
                                    "Name": tg["Name"],
                                    "ID": tg["ID"],
                                    "Additional Info": f"Protocol: {tg['Protocol']}, Port: {tg['Port']}, Health Check: {tg['HealthCheckProtocol']}, Target Type: {tg['TargetType']}",
                                }
                            )

                            # Add instances with more details
                            for instance in tg["Instances"]:
                                rows.append(
                                    {
                                        "Resource Type": "Instance",
                                        "Name": instance["Name"],
                                        "ID": instance["ID"],
                                        "Additional Info": f"Type: {instance['Type']}, State: {instance['State']}, IP: {instance.get('Private IP', 'N/A')}, Target Health: {instance['Target Health']}",
                                    }
                                )

                            # Add databases if any
                            for db in tg["Databases"]:
                                rows.append(
                                    {
                                        "Resource Type": "Database",
                                        "Name": db["Name"],
                                        "ID": db["ID"],
                                        "Additional Info": f"Engine: {db['Engine']}, Status: {db['Status']}",
                                    }
                                )

                        df = pd.DataFrame(rows)

                        # Only create sheet if we have data
                        if not df.empty:
                            df.to_excel(writer, sheet_name=sheet_name, index=False)

                            worksheet = writer.sheets[sheet_name]
                            for idx, col in enumerate(df.columns):
                                max_length = max(
                                    df[col].astype(str).apply(len).max(), len(col)
                                )
                                worksheet.column_dimensions[chr(65 + idx)].width = min(
                                    max_length + 2, 50
                                )

                    except Exception as e:
                        print(f"Warning: Error processing sheet {sheet_name}: {str(e)}")
                        continue

        except Exception as e:
            raise Exception(f"Error saving Excel file: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="Map AWS resource dependencies from inventory Excel file"
    )
    parser.add_argument("input_file", help="Path to the AWS inventory Excel file")
    parser.add_argument(
        "output_file", help="Path where to save the dependency mapping Excel file"
    )

    args = parser.parse_args()

    mapper = AWSDependencyMapper(args.input_file)
    mapper.export_dependencies(args.output_file)
    print(f"Dependency mapping has been exported to {args.output_file}")


if __name__ == "__main__":
    main()
