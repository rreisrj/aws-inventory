# Fix for aws_components/__init__.py
"""AWS resource inventory components package."""

from typing import Any, Dict, List

from .apigateway import APIGatewayComponent
from .autoscaling import AutoScalingComponent
from .cloudfront import CloudFrontComponent
from .dynamodb import DynamoDBComponent
from .ec2 import EC2Component
from .ecr import ECRComponent
from .ecs import ECSComponent
from .efs import EFSComponent  # Added EFS
from .eks import EKSComponent
from .elb import ELBComponent
from .gateway import GatewayComponent
from .kms import KMSComponent  # Added KMS
from .lambda_component import LambdaComponent
from .rds import RDSComponent
from .route53 import Route53Component
from .s3 import S3Component
from .sns import SNSComponent
from .sqs import SQSComponent
from .unattached_ebs import UnattachedEBSComponent
from .unattached_eip import UnattachedEIPComponent
from .unattached_eni import UnattachedENIComponent
from .unattached_sg import UnattachedSGComponent
from .vpc import VPCComponent

__all__ = [
    "APIGatewayComponent",
    "AutoScalingComponent",
    "DynamoDBComponent",
    "CloudFrontComponent",
    "EC2Component",
    "ECRComponent",
    "ECSComponent",
    "EFSComponent",
    "EKSComponent",
    "ELBComponent",
    "GatewayComponent",
    "KMSComponent",
    "LambdaComponent",
    "RDSComponent",
    "Route53Component",
    "S3Component",
    "SNSComponent",
    "SQSComponent",
    "UnattachedEBSComponent",
    "UnattachedSGComponent",
    "UnattachedEIPComponent",
    "UnattachedENIComponent",
    "VPCComponent",
]

# Component mapping for easier access
COMPONENT_MAP = {
    "APIGateway": APIGatewayComponent,
    "AutoScaling": AutoScalingComponent,
    "DynamoDB": DynamoDBComponent,
    "CloudFront": CloudFrontComponent,
    "EC2": EC2Component,
    "ECR": ECRComponent,
    "ECS": ECSComponent,
    "EFS": EFSComponent,  # Added
    "EKS": EKSComponent,
    "ELB": ELBComponent,
    "Gateway": GatewayComponent,
    "KMS": KMSComponent,  # Added
    "Lambda": LambdaComponent,
    "RDS": RDSComponent,
    "Route53": Route53Component,
    "S3": S3Component,
    "SNS": SNSComponent,
    "SQS": SQSComponent,
    "UnattachedEBS": UnattachedEBSComponent,
    "UnattachedSG": UnattachedSGComponent,
    "UnattachedEIP": UnattachedEIPComponent,
    "UnattachedENI": UnattachedENIComponent,
    "VPC": VPCComponent,
}


def get_component(service_name: str, session) -> Any:
    """Return the appropriate component for a service.

    Args:
        service_name: Name of the AWS service
        session: AWS session to use

    Returns:
        Component instance for the specified service
    """
    component_class = COMPONENT_MAP.get(service_name)
    if component_class:
        return component_class(session)
    return None


def get_available_services() -> List[str]:
    """Return list of available services.

    Returns:
        List of supported service names
    """
    return list(COMPONENT_MAP.keys())


def initialize_all_components(session) -> Dict[str, Any]:
    """Initialize all available components.

    Args:
        session: AWS session to use

    Returns:
        Dictionary of service name to component instance
    """
    return {
        service: component_class(session)
        for service, component_class in COMPONENT_MAP.items()
    }


# Version info
__version__ = "1.0.0"
__author__ = "AWS Account Inventory"
__description__ = "AWS Resource Inventory Components"
