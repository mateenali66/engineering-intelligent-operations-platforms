# Single provider-requirements block for the clean module. Terraform requires
# exactly one `required_providers` per module, so it lives here and main.tf and
# device-plugin.tf reference these providers without redeclaring them.

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}
