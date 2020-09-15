resource "aws_sqs_queue" "queue" {
  name = "${var.project_name}-queue"

  tags = {
    Name   = "${var.project_name}-queue"
  }
}


output "arn" {
  value = aws_sqs_queue.queue.arn
}


output "name" {
  value = aws_sqs_queue.queue.name
}
