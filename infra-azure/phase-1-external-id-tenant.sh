#!/usr/bin/env bash
# Phase 1 -- Entra External Identities (CIAM) tenant for customer auth.
#
# Creates a NEW Entra tenant separate from the management/workforce
# tenant. Parents, teachers, and (indirectly) kids will authenticate
# against this customer tenant.
#
# Idempotent: re-running on an existing tenant returns the same shape.
#
# Run with:
#   bash infra-azure/phase-1-external-id-tenant.sh
#
# Prerequisites: az CLI authenticated against tenant
# 3b7e8876-fd7e-4b71-b14f-f1bf9beb8e05 (brian@dragonfly-app.net).

set -euo pipefail

SUB="5a04114f-9102-4e0b-828b-b385096edfbc"
RG="dragonfly-dev-rg"
CIAM_RESOURCE_NAME="dragonflyCustomers"

URL="https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.AzureActiveDirectory/ciamDirectories/${CIAM_RESOURCE_NAME}?api-version=2023-05-17-preview"

echo "==> ensure Microsoft.AzureActiveDirectory provider is registered"
az provider register --namespace Microsoft.AzureActiveDirectory --subscription "$SUB" > /dev/null

echo "==> PUT ciamDirectory ${CIAM_RESOURCE_NAME}"
az rest --method put --url "$URL" --body '{
  "location": "United States",
  "sku": {"name": "Standard", "tier": "A0"},
  "properties": {
    "createTenantProperties": {
      "displayName": "Dragonfly Customers",
      "countryCode": "US"
    }
  }
}' --subscription "$SUB" > /dev/null

echo "==> poll until provisioning succeeds"
for i in $(seq 1 30); do
  RESP=$(az rest --method get --url "$URL" --subscription "$SUB" 2>/dev/null)
  STATE=$(echo "$RESP" | grep -oE '"provisioningState":[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
  TID=$(echo "$RESP" | grep -oE '"tenantId":[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
  echo "  state=$STATE tid=$TID"
  case "$STATE" in
    Succeeded) break ;;
    Failed|Canceled) echo "FAILED"; exit 1 ;;
  esac
  sleep 15
done

echo "done. Customer tenant ID: $TID"
echo
echo "Next: log in to the customer tenant so app registrations can be"
echo "created against it. Run:"
echo
echo "  az login --tenant $TID"
echo
echo "(brian@dragonfly-app.net auto-gets Global Administrator on the new"
echo "tenant as the creator.)"
