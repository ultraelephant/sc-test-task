provider "aws" {
	access_key = "${var.access_key}"
	secret_key = "${var.secret_key}"
	region = "${var.region}"
}


module "s3" {
  source = "./modulestf/s3"

  project_name = "${var.project_name}"
}


module "sqs" {
  source = "./modulestf/sqs"

  project_name = "${var.project_name}"
}


module "lamdba" {
  source = "./modulestf/lambda"

  project_name = "${var.project_name}"
  s3_arn = "${module.s3.arn}"
  sqs_arn = "${module.sqs.arn}"
  sqs_name = "${module.sqs.name}"
  s3_id = "${module.s3.id}"
}