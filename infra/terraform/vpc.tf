# Two availability zones, one public + one private subnet in each.
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  subnet_layout = {
    a = { az = data.aws_availability_zones.available.names[0], public_index = 0, private_index = 10 }
    b = { az = data.aws_availability_zones.available.names[1], public_index = 1, private_index = 11 }
  }

  eks_cluster_name = "${var.project_name}-${var.environment}-eks"
}

resource "aws_vpc" "mlops" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-${var.environment}-vpc" }
}

resource "aws_internet_gateway" "mlops" {
  vpc_id = aws_vpc.mlops.id
  tags   = { Name = "${var.project_name}-${var.environment}-igw" }
}

resource "aws_subnet" "public" {
  for_each = local.subnet_layout

  vpc_id                  = aws_vpc.mlops.id
  availability_zone       = each.value.az
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value.public_index)
  map_public_ip_on_launch = true

  tags = {
    Name                     = "${var.project_name}-${var.environment}-public-${each.key}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_subnet" "private" {
  for_each = local.subnet_layout

  vpc_id                  = aws_vpc.mlops.id
  availability_zone       = each.value.az
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value.private_index)
  map_public_ip_on_launch = false

  tags = {
    Name                              = "${var.project_name}-${var.environment}-private-${each.key}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.mlops.id
  tags   = { Name = "${var.project_name}-${var.environment}-public-rt" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.mlops.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# One NAT gateway is cost-conscious for a lab, but NOT multi-AZ resilient.
resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${var.project_name}-${var.environment}-nat-eip" }
}

resource "aws_nat_gateway" "mlops" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public["a"].id

  depends_on = [aws_internet_gateway.mlops]
  tags       = { Name = "${var.project_name}-${var.environment}-nat" }
}

# Both private AZs use the same NAT (cross-AZ data charges possible).
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.mlops.id
  tags   = { Name = "${var.project_name}-${var.environment}-private-rt" }
}

resource "aws_route" "private_egress" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.mlops.id
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}
