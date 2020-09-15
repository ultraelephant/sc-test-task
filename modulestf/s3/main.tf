resource "aws_s3_bucket" "csv" {
  bucket = "${var.project_name}-bucket"
  acl    = "private"

  tags = {
    Name   = "${var.project_name}-bucket"
  }
}


output "arn" {
  value = aws_s3_bucket.csv.arn
}


output "id" {
  value = aws_s3_bucket.csv.id
}
