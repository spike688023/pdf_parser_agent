#!/bin/bash
echo "🛑 Stopping Monitoring Stack (Scaling to 0)..."

NAMESPACE="monitoring"

# 1. Scale Deployments to 0
kubectl scale deployment -n $NAMESPACE --replicas=0 --all

# 2. Scale StatefulSets to 0 (Prometheus uses StatefulSet)
kubectl scale statefulset -n $NAMESPACE --replicas=0 --all

# 3. Delete DaemonSets (Node Exporter usually runs as DaemonSet, cannot scale to 0)
# We use 'patch' to make it not schedule on any node, effectively 0 pods.
kubectl patch daemonset -n $NAMESPACE prometheus-prometheus-node-exporter -p '{"spec": {"template": {"spec": {"nodeSelector": {"non-existing": "true"}}}}}' || true

echo "✅ Monitoring stack stopped. (Resources are now free)"
