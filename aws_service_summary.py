# aws_service_summary.py
import concurrent.futures
import configparser
import os
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock

import boto3
import botocore
import openpyxl
import pandas as pd
from botocore.exceptions import ClientError
from openpyxl.styles import Font, PatternFill

from aws_components import initialize_all_components


class AWSResourceInventory:
    def __init__(self):
        self.session = None
        self.account_id = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.resources = {}
        self.resources_lock = Lock()  # Add lock for thread safety
        self.instance_counts = {}
        self.rds_instance_counts = {}
        self.regions = []
        self.available_regions = [
            "us-east-1",
            "us-east-2",
            "sa-east-1",
            "us-west-1",
            "us-west-2",
        ]
        # Updated to include EFS and KMS
        self.supported_services = [
            "APIGateway",
            "AutoScaling",
            "CloudFront",
            "DynamoDB",
            "EC2",
            "ECR",
            "ECS",
            "EFS",
            "EKS",
            "ELB",
            "Gateway",
            "KMS",
            "Lambda",
            "RDS",
            "Route53",
            "S3",
            "SNS",
            "SQS",
            "Subnets",  # Changed from "Subnet" to "Subnets" to match COMPONENT_MAP
            "TargetGroup",
            "UnattachedEBS",
            "UnattachedSG",
            "UnattachedEIP",
            "UnattachedENI",
            "VPC",
        ]
        # Define dependency-related services
        self.dependency_services = [
            "Gateway",
            "ELB",
            "TargetGroup",
            "EC2",
            "EKS",
            "RDS",
        ]
        self.components = {}

    def select_regions(self):
        """Let user select which regions to scan"""
        print("\nAvailable regions:")
        for i, region in enumerate(self.available_regions, 1):
            print(f"{i}. {region}")

        print("\nSelect regions (comma-separated numbers, or 'all' for all regions)")
        while True:
            selection = input("\nEnter selection: ").strip().lower()
            if selection == "all":
                self.regions = self.available_regions
                break
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                if all(0 <= i < len(self.available_regions) for i in indices):
                    self.regions = [self.available_regions[i] for i in indices]
                    break
            except ValueError:
                print(
                    "Invalid input. Please enter numbers separated by commas or 'all'"
                )

    def get_aws_profile(self):
        """List and select AWS profile"""
        profiles = self._list_profiles()
        if not profiles:
            print("No AWS profiles found.")
            sys.exit(1)

        print("\nAvailable AWS profiles:")
        for i, profile in enumerate(profiles, 1):
            print(f"{i}. {profile}")

        while True:
            try:
                index = int(input("\nSelect profile number: ")) - 1
                if 0 <= index < len(profiles):
                    return profiles[index]
            except ValueError:
                pass
            print("Invalid selection. Please try again.")

    def _list_profiles(self):
        """Get list of AWS profiles"""
        profiles = set()
        aws_folder = Path.home() / ".aws"

        # Check credentials file
        credentials_path = aws_folder / "credentials"
        if credentials_path.exists():
            config = configparser.ConfigParser()
            config.read(credentials_path)
            profiles.update(config.sections())

        # Check config file
        config_path = aws_folder / "config"
        if config_path.exists():
            config = configparser.ConfigParser()
            config.read(config_path)
            for section in config.sections():
                # Remove 'profile ' prefix if present
                profile_name = section.replace("profile ", "")
                profiles.add(profile_name)

        if not profiles:
            print("\nNo AWS profiles found in ~/.aws/credentials or ~/.aws/config")
            print("Please configure your AWS credentials first using 'aws configure'")
            sys.exit(1)

        return sorted(profiles)

    def initialize_components(self):
        """Initialize all service components"""
        self.components = initialize_all_components(self.session)

    def initialize_session(self, profile):
        """Initialize AWS session"""
        try:
            print(f"\nInitializing AWS session with profile: {profile!r}")
            self.session = boto3.Session(profile_name=profile)

            # Test the session by making a simple API call
            sts = self.session.client("sts")
            caller_identity = sts.get_caller_identity()
            self.account_id = caller_identity["Account"]

            # Initialize components after session is created
            self.initialize_components()
            return True
        except ClientError as e:
            if "InvalidClientTokenId" in str(e):
                print(f"\nError: Invalid AWS credentials for profile {profile!r}")
            elif "ExpiredToken" in str(e):
                print(f"\nError: AWS credentials for profile {profile!r} have expired")
            else:
                print(f"\nAWS Error: {str(e)}")
            return False
        except Exception as e:
            print(f"\nError initializing session: {str(e)}")
            print("Please verify your AWS credentials and try again")
            return False

    def collect_region_resources(self, region, selected_services=None):
        """Collect resources for a specific region"""
        print(f"\nCollecting resources in {region}...")
        region_resources = []

        # If no specific services selected, use all components
        services_to_scan = selected_services or self.components.keys()

        for service in services_to_scan:
            if service not in self.components:
                print(f"  Warning: {service} is not a valid service component")
                continue

            component = self.components[service]
            try:
                print(f"  Collecting {service} resources in {region}...")
                resources = component.get_resources(region)

                # Skip empty resource lists
                if not resources:
                    print(f"  No {service} resources found in {region}")
                    continue

                # Add resources to the list
                region_resources.extend(resources)

                # Update resource counts
                count = len(resources)
                print(f"  Found {count} {service} resources in {region}")

                # Thread-safe update of instance counts
                with self.resources_lock:
                    if service not in self.instance_counts:
                        self.instance_counts[service] = {}
                    if region not in self.instance_counts[service]:
                        self.instance_counts[service][region] = 0
                    self.instance_counts[service][region] = count

            except Exception as e:
                print(f"  Error collecting {service} resources in {region}: {str(e)}")
                continue

        # Thread-safe update of resources dictionary
        with self.resources_lock:
            self.resources[region] = region_resources

        return region

    def collect_resources(self, selected_services=None):
        """Collect resources across selected regions using parallel processing"""
        if not self.session:
            print(
                "AWS session not initialized. Please call initialize_session() first."
            )
            return False

        print("\nCollecting resources from regions:")
        for region in self.regions:
            print(f"- {region}")

        if selected_services:
            print("\nScanning only these services:")
            for service in selected_services:
                print(f"- {service}")

        # Use ThreadPoolExecutor with max_workers=2 for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all regions for processing
            future_to_region = {
                executor.submit(
                    self.collect_region_resources, region, selected_services
                ): region
                for region in self.regions
            }

            # Process completed futures
            for future in concurrent.futures.as_completed(future_to_region):
                region = future_to_region[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing region {region}: {str(e)}")

    def select_services(self, dependency_mode=False):
        """Let user select which services to scan"""
        if dependency_mode:
            print("\nRunning in dependency mapping mode. Will collect these services:")
            for service in self.dependency_services:
                print(f"- {service}")
            return self.dependency_services

        print("\nAvailable services:")
        for i, service in enumerate(self.supported_services, 1):
            print(f"{i}. {service}")

        while True:
            try:
                selection = input(
                    "\nEnter service numbers (comma-separated) or 'all': "
                ).strip()
                if selection.lower() == "all":
                    return self.supported_services

                selected_indices = [int(x.strip()) for x in selection.split(",")]
                selected_services = [
                    self.supported_services[i - 1]
                    for i in selected_indices
                    if 0 < i <= len(self.supported_services)
                ]
                return selected_services
            except (ValueError, IndexError):
                print("Invalid selection. Please try again.")

    def export_to_excel(self, selected_services=None):
        """Export collected resources to Excel"""
        if not self.resources:
            print("No resources collected. Please call collect_resources() first.")
            return False

        try:
            # Create a new workbook
            wb = openpyxl.Workbook()
            wb.remove(wb.active)  # Remove default sheet

            # Create summary sheet
            summary_ws = wb.create_sheet("Summary")

            # Style definitions
            header_fill = PatternFill(
                start_color="1F4E78", end_color="1F4E78", fill_type="solid"
            )
            header_font = Font(color="FFFFFF", bold=True, size=20)
            regular_font = Font(size=20)

            # Write summary headers
            summary_headers = ["Service", "Total Resources", "Regions"]
            for col, header in enumerate(summary_headers, 1):
                cell = summary_ws.cell(row=1, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font

            # Calculate summary data
            summary_data = {}
            for region, region_resources in self.resources.items():
                for resource in region_resources:
                    service = resource["Service"]
                    if service not in summary_data:
                        summary_data[service] = {"count": 0, "regions": set()}
                    summary_data[service]["count"] += 1
                    summary_data[service]["regions"].add(region)

            # Write summary data
            for row, (service, data) in enumerate(sorted(summary_data.items()), 2):
                # Service name
                cell = summary_ws.cell(row=row, column=1, value=service)
                cell.font = regular_font

                # Total resources
                cell = summary_ws.cell(row=row, column=2, value=data["count"])
                cell.font = regular_font

                # Regions
                cell = summary_ws.cell(
                    row=row, column=3, value=", ".join(sorted(data["regions"]))
                )
                cell.font = regular_font

            # Adjust column widths
            for col in range(1, len(summary_headers) + 1):
                max_length = 0
                for row in range(1, summary_ws.max_row + 1):
                    cell_value = str(summary_ws.cell(row=row, column=col).value)
                    max_length = max(max_length, len(cell_value))
                summary_ws.column_dimensions[chr(64 + col)].width = min(
                    max_length + 2, 50
                )

            # Critical fields that should always appear first
            critical_fields = [
                "Region",
                "Service",
                "Subnet Name",
                "Resource ID",
                "Description",
                "Creation Time",
            ]

            # Group resources by service
            service_resources = {}
            for region_resources in self.resources.values():
                for resource in region_resources:
                    service = resource["Service"]
                    if service not in service_resources:
                        service_resources[service] = []
                    service_resources[service].append(resource)

            # Create detail sheets
            for service, resources in service_resources.items():
                if not resources:
                    continue

                # Create a sheet name that's valid for Excel
                sheet_name = service.replace(" ", "_")[:31]
                ws = wb.create_sheet(sheet_name)

                # Get all headers from data
                all_headers = set()
                for resource in resources:
                    all_headers.update(resource.keys())

                # Sort headers with critical fields first
                headers = critical_fields + sorted(all_headers - set(critical_fields))

                # Write headers
                for col, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col, value=header)
                    cell.fill = header_fill
                    cell.font = header_font

                # Write data
                for row, resource in enumerate(resources, 2):
                    for col, header in enumerate(headers, 1):
                        value = resource.get(header, "")
                        cell = ws.cell(row=row, column=col, value=str(value))
                        cell.font = regular_font

            # Save the workbook with timestamp
            output_file = (
                f"dependencies_aws_inventory_{self.timestamp}.xlsx"
                if selected_services == self.dependency_services
                else f"aws_inventory_{self.timestamp}.xlsx"
            )
            try:
                wb.save(output_file)
                print(f"\nExcel file saved as: {output_file}")
                return True
            except Exception as e:
                print(f"Error saving Excel file: {str(e)}")
                return False

        except Exception as e:
            print(f"Error creating Excel file: {str(e)}")
            return False


def main():
    """Main function"""
    import argparse

    inventory = AWSResourceInventory()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AWS Resource Inventory Tool")
    parser.add_argument(
        "--dependencies", action="store_true", help="Run in dependency mapping mode"
    )
    parser.add_argument(
        "--profile",
        help="AWS profile to use. If not specified, will prompt for selection",
    )
    args = parser.parse_args()

    # Get AWS profile
    profile = args.profile if args.profile else inventory.get_aws_profile()
    if not profile:
        print("No AWS profile selected. Exiting.")
        sys.exit(1)

    # Initialize AWS session
    if not inventory.initialize_session(profile):
        print("Failed to initialize AWS session. Exiting.")
        sys.exit(1)

    # Select regions
    inventory.select_regions()

    # Initialize components
    inventory.initialize_components()

    # Select services based on mode
    selected_services = inventory.select_services(args.dependencies)

    # Collect resources
    print("\nCollecting resources...")
    inventory.collect_resources(selected_services)

    # Export to Excel
    if args.dependencies:
        inventory_file = f"dependencies_aws_inventory_{inventory.timestamp}.xlsx"
    else:
        inventory_file = f"aws_inventory_{inventory.timestamp}.xlsx"
    print(f"\nExporting inventory to {inventory_file}...")
    success = inventory.export_to_excel(selected_services)

    # If in dependencies mode and export was successful, create dependency mapping
    if args.dependencies and success:
        from aws_dependency_mapper import AWSDependencyMapper

        dependency_file = f"dependencies_aws_topology_{inventory.timestamp}.xlsx"
        print(f"\nGenerating dependency mapping to {dependency_file}...")
        try:
            mapper = AWSDependencyMapper(inventory_file)
            mapper.export_dependencies(dependency_file)
            print(f"Dependency mapping has been exported to {dependency_file}")
        except Exception as e:
            print(f"Error generating dependency mapping: {str(e)}")
            print("The inventory file was still created successfully.")

    if success:
        print("\nInventory process completed successfully!")
    else:
        print("\nInventory export failed.")


if __name__ == "__main__":
    main()
