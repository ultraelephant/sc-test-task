locals {
  source_files = ["./lambda_function.py"]
}


data "template_file" "t_file" {
  count = "${length(local.source_files)}"
  template = "${file(element(local.source_files, count.index))}"
}


resource "local_file" "to_temp_dir" {
  count    = "${length(local.source_files)}"
  filename = "${path.module}/temp/${basename(element(local.source_files, count.index))}"
  content  = "${element(data.template_file.t_file.*.rendered, count.index)}"
}


data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "lambda.zip"
  source_dir = "${path.module}/temp"

  depends_on = [
    "local_file.to_temp_dir",
  ]
}


output "path" {
  value = data.archive_file.lambda_zip.output_path
}


output "payload" {
  value = data.archive_file.lambda_zip.output_base64sha256
}