# Cloud DNS — dragonfly-app.net
#
# STATUS: stub. The zone and records were created via gcloud during the
# 2026-05-05 migration from Squarespace. This file is the future home of
# Terraform state for the zone but is NOT YET importing the live resources.
#
# To bring the live zone under Terraform management:
#
#   cd infra-gcp/dns
#   terraform init
#   terraform import google_dns_managed_zone.dragonfly_app \
#     projects/dragonflyapp-495423/managedZones/dragonfly-app-zone
#   terraform plan      # should show no diff once the resource matches
#
# Each record set must be imported separately, e.g.:
#
#   terraform import 'google_dns_record_set.apex_a' \
#     projects/dragonflyapp-495423/managedZones/dragonfly-app-zone/dragonfly-app.net./A
#
# Until the broader infra-gcp/ reorganization decides on Terraform vs.
# gcloud scripts (see ADR 0005 follow-ups), all DNS changes go through
# `gcloud dns record-sets transaction` — see docs/runbook.md.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "dragonflyapp-495423"
}

resource "google_dns_managed_zone" "dragonfly_app" {
  name        = "dragonfly-app-zone"
  dns_name    = "dragonfly-app.net."
  description = "Dragonfly app domain — migrated from Squarespace 2026-05-05"
  visibility  = "public"
}

# Record sets are managed via gcloud at this stage. Add
# google_dns_record_set blocks here as part of the infra-gcp reorg.
#
# Inventory at migration time (see docs/runbook.md for live values):
#   - dragonfly-app.net.                   A      (4 Squarespace IPs, TTL 14400)
#   - dragonfly-app.net.                   MX     (1 smtp.google.com., TTL 3600)
#   - dragonfly-app.net.                   TXT    (SPF, TTL 3600)
#   - google._domainkey.dragonfly-app.net. TXT    (DKIM, TTL 3600)
#   - www.dragonfly-app.net.               CNAME  (ext-sq.squarespace.com., TTL 14400)
#   - api.dragonfly-app.net.               CNAME  (ghs.googlehosted.com., TTL 300)
