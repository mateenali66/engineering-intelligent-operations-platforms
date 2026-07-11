# Supporting resources for Listing 4-2: the node IAM role and the input
# variable the EKS node group depends on. Kept out of the printed listing for
# focus, but required for `terraform validate` and `terraform plan` to succeed.

variable "subnet_ids" {
  type        = list(string)
  description = "Subnets the GPU node group runs in. The default is a plan-time placeholder (the provider requires at least one item); supply real subnet IDs to deploy."
  default     = ["subnet-0a1b2c3d4e5f67890"]
}

resource "aws_iam_role" "node" {
  name = "gpu-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "worker" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "cni" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}
