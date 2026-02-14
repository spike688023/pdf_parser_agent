#!/bin/bash
echo "🛑 Stopping Monitoring Stack (Scaling to 0)..."

NAMESPACE="monitoring"

# 1. Scale Deployments to 0
kubectl scale deployment -n $NAMESPACE --replicas=0 --all

# 2. Scale StatefulSets to 0 (Prometheus uses StatefulSet)
kubectl scale statefulset -n $NAMESPACE --replicas=0 --all

# 3. Stop all DaemonSets by patching nodeSelector to something impossible
# Use a loop to avoid error if no DaemonSets exist or specific name is wrong
for ds in $(kubectl get daemonset -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}'); do
    echo "  - Patching DaemonSet: $ds to stop scheduling..."
    kubectl patch daemonset $ds -n $NAMESPACE -p '{"spec": {"template": {"spec": {"nodeSelector": {"non-existing": "true"}}}}}'
done

echo "✅ Monitoring stack stopped. (Resources are now free)"
