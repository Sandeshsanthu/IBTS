data "aws_region" "current" {}

data "aws_ami" "amazon_linux" {
    most_recent = true
    owners =   ["amazon"]

    filter {
      name = "name"
      values = ["amzn2-ami-hvm-*-x86_64-gp2"]
}
}

resource "aws_instance" "my_instance" {
    ami           = data.aws_ami.amazon_linux.id
    instance_type = "t3.micro" 
    instance_initiated_shutdown_behavior = "stop"

    root_block_device {
      volume_type = "gp3"
      volume_size = 10
      delete_on_termination = true
    }
     tags = {
    Name = "AutoStop-Idle-Instance"
  }
}
