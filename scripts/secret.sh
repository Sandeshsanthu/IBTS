API_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
kubectl create secret generic api-gateway-secrets -n ibts-app \
  --from-literal=API_KEY="$API_KEY" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -
unset API_KEY JWT_SECRET

kubectl rollout restart deploy/api-gateway -n ibts-app
kubectl rollout status deploy/api-gateway -n ibts-app --timeout=240s

 kubectl get secret api-gateway-secrets -n ibts-app -o json | jq -r '.data | to_entries[] | "\(.key) len=\(.value | @base64d | length)"'

 kubectl -n ibts-app get secret api-gateway-secrets -o jsonpath='{.data.API_KEY}' | base64 -d; echo
 $env:IBTS_API_KEY = 
