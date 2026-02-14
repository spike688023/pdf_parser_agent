#!/bin/bash
echo "🚀 Starting Monitoring Stack..."

NAMESPACE="monitoring"

# 1. Scale Deployments Back (Grafana, Operator, etc.)
kubectl scale deployment -n $NAMESPACE --replicas=1 monitoring-grafana
kubectl scale deployment -n $NAMESPACE --replicas=1 monitoring-kube-prometheus-operator
kubectl scale deployment -n $NAMESPACE --replicas=1 monitoring-kube-state-metrics

# 2. Scale StatefulSets Back (Prometheus)
kubectl scale statefulset -n $NAMESPACE --replicas=1 prometheus-monitoring-kube-prometheus-prometheus

# 3. Restore DaemonSets (Node Exporter)
# Remove the fake selector so it can schedule again.
kubectl patch daemonset -n $NAMESPACE prometheus-prometheus-node-exporter --type=json -p='[{"op": "remove", "path": "/spec/template/spec/nodeSelector/non-existing"}]' || true

echo "✅ Monitoring stack started!"
echo ""
echo "Wait a few seconds for pods to become ready."
