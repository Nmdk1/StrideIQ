#!/usr/bin/env bash
set -e
echo '--- LANDING HEAD ---'
curl -sI https://strideiq.run/ | head -5
echo ''
echo '--- New copy present ---'
curl -s https://strideiq.run/ | grep -oE '(Your body has a voice|Cancel anytime via Stripe|Deep Intelligence\. Zero Fluff|Adam S\.)' | sort -u
echo ''
echo '--- Old copy (should be empty) ---'
curl -s https://strideiq.run/ | grep -oE '(No credit card required|AI Running Coach vs Human Running Coach)' | sort -u || true
echo ''
echo '--- URL STATUS ---'
for url in https://strideiq.run/ https://strideiq.run/case-studies https://strideiq.run/case-studies/dexa-and-the-7-pound-gap https://strideiq.run/case-studies/strength-and-durability https://strideiq.run/mission https://strideiq.run/tools/training-pace-calculator; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url")
  echo "$code  $url"
done
echo ''
echo '--- DEXA case study spot-check ---'
curl -s https://strideiq.run/case-studies/dexa-and-the-7-pound-gap | grep -oE '(7 lbs of mineral density|DEXA|T-score)' | sort -u | head -5
echo ''
echo '--- Strength case study spot-check ---'
curl -s https://strideiq.run/case-studies/strength-and-durability | grep -oE '(cardiac decoupling|hip thrusts|RDLs)' | sort -u | head -5
