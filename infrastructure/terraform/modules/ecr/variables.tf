variable "repository_name" {
  description = "Private application repository name."
  type        = string
}

variable "release_image_count" {
  description = "Retain this many images tagged sha-<full commit SHA>."
  type        = number
  default     = 20

  validation {
    condition     = var.release_image_count >= 1 && floor(var.release_image_count) == var.release_image_count
    error_message = "Release image retention must be a positive integer."
  }
}

variable "tags" {
  description = "Project and environment tags."
  type        = map(string)
  default     = {}
}
